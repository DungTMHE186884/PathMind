"""R&D document store and tree import/export. Every action is audit-logged.

Documents are the evidence layer: the original file is kept on disk, its text
in ``knowledge_sources`` (used by the tree and, later, by retrieval).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from sqlalchemy.orm import Session

from pathmind.database.models import KnowledgeDomain, KnowledgeNode, KnowledgeSource
from pathmind.services import audit

from . import ingest
from .service import TreeError, _clean, _create_domain, _now, _require_edit, can_edit

MAX_IMPORT_NODES = 5000
EXPORT_FORMAT = "pathmind-knowledge-tree"
EXPORT_VERSION = 1

_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".txt": "text/plain",
}


def _blob_dir() -> Path:
    from pathmind.multi_user.paths import SYSTEM_ROOT

    path = SYSTEM_ROOT / "store-documents"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(filename: str) -> str:
    name = re.sub(r"[^\w.\- ]+", "_", (filename or "file").strip())[:200]
    return name or "file"


def _doc_dict(s: KnowledgeSource, domain_name: str = "") -> dict:
    return {
        "id": s.id,
        "domain_id": s.domain_id,
        "domain_name": domain_name,
        "filename": s.filename,
        "size": s.size,
        "sha256": s.sha256,
        "downloadable": bool(s.blob_path),
        "uploaded_by": s.uploaded_by,
        "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
    }


def list_documents(db: Session, role: str, domain_id: str | None = None) -> list[dict]:
    _require_edit(role)
    names = {d.id: d.name for d in db.query(KnowledgeDomain).all()}
    q = db.query(KnowledgeSource)
    if domain_id:
        q = q.filter(KnowledgeSource.domain_id == domain_id)
    return [_doc_dict(s, names.get(s.domain_id, "")) for s in q.order_by(KnowledgeSource.created_at.desc()).all()]


def store_original(source: KnowledgeSource, filename: str, data: bytes, db: Session | None = None) -> None:
    """Keep the uploaded file (in the default storage) next to its extracted text."""
    from pathmind.services.storage import object_store

    ext = Path(filename).suffix.lower()
    source.content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")
    source.blob_path = object_store.save("store-documents", f"{source.id}{ext}", data, source.content_type, db=db)


def upload_document(
    db: Session, role: str, user_id: str, *, domain_id: str, filename: str, data: bytes
) -> dict:
    """Add a document to a domain's store without touching the tree."""
    _require_edit(role)
    domain = db.get(KnowledgeDomain, domain_id)
    if domain is None:
        raise TreeError(404, "Domain not found.")
    try:
        text = ingest.extract_text(filename, data)
    except ingest.IngestError as exc:
        raise TreeError(400, str(exc)) from exc
    sha = hashlib.sha256(data).hexdigest()
    dup = (
        db.query(KnowledgeSource)
        .filter(KnowledgeSource.domain_id == domain_id, KnowledgeSource.sha256 == sha)
        .first()
    )
    if dup is not None:
        raise TreeError(409, f"This file is already in the store as “{dup.filename}”.")
    source = KnowledgeSource(
        domain_id=domain_id,
        filename=_clean(filename, 255) or "file",
        size=len(data),
        sha256=sha,
        text=text,
        uploaded_by=user_id,
    )
    db.add(source)
    db.flush()
    store_original(source, filename, data, db)
    audit.record(
        db, user_id, "store.document.upload", target_type="document", target_id=source.id,
        data={"filename": source.filename, "size": source.size, "domain_id": domain_id}, commit=False,
    )
    db.commit()
    return _doc_dict(source, domain.name)


def read_document(db: Session, role: str, user_id: str, document_id: str) -> tuple[bytes, str, str]:
    """Original bytes of a stored document (falls back to the extracted text)."""
    _require_edit(role)
    source = db.get(KnowledgeSource, document_id)
    if source is None:
        raise TreeError(404, "Document not found.")
    audit.record(
        db, user_id, "store.document.download", target_type="document", target_id=source.id,
        data={"filename": source.filename},
    )
    if source.blob_path:
        from pathmind.services.storage import object_store

        try:
            return object_store.load(source.blob_path), source.content_type or "application/octet-stream", source.filename
        except object_store.StorageError:
            pass  # fall back to the extracted text below
    return source.text.encode("utf-8"), "text/plain; charset=utf-8", Path(source.filename).stem + ".txt"


def delete_document(db: Session, role: str, user_id: str, document_id: str) -> None:
    _require_edit(role)
    source = db.get(KnowledgeSource, document_id)
    if source is None:
        raise TreeError(404, "Document not found.")
    used = db.query(KnowledgeNode).filter(KnowledgeNode.domain_id == source.domain_id).all()
    if any(r.get("source_id") == source.id for n in used for r in (n.refs or [])):
        raise TreeError(409, "Tree nodes still point into this document. Delete or move them first.")
    if source.blob_path:
        from pathmind.services.storage import object_store

        object_store.remove(source.blob_path)
    audit.record(
        db, user_id, "store.document.delete", target_type="document", target_id=source.id,
        data={"filename": source.filename}, commit=False,
    )
    db.delete(source)
    db.commit()


# ── tree export / import ──────────────────────────────────────────────────


def export_tree(db: Session, role: str, user_id: str, domain_id: str) -> dict[str, Any]:
    _require_edit(role)
    domain = db.get(KnowledgeDomain, domain_id)
    if domain is None:
        raise TreeError(404, "Domain not found.")
    nodes = (
        db.query(KnowledgeNode)
        .filter(KnowledgeNode.domain_id == domain_id)
        .order_by(KnowledgeNode.position)
        .all()
    )
    sources = db.query(KnowledgeSource).filter(KnowledgeSource.domain_id == domain_id).all()
    payload = {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": _now().isoformat() + "Z",
        "domain": {"name": domain.name, "description": domain.description, "slug": domain.slug},
        "nodes": [
            {
                "id": n.id,
                "parent_id": n.parent_id,
                "title": n.title,
                "summary": n.summary,
                "position": n.position,
                "refs": n.refs or [],
            }
            for n in nodes
        ],
        "sources": [{"id": s.id, "filename": s.filename, "size": s.size, "sha256": s.sha256} for s in sources],
    }
    audit.record(
        db, user_id, "store.tree.export", target_type="domain", target_id=domain_id,
        data={"nodes": len(nodes)},
    )
    return payload


def import_tree(db: Session, role: str, user_id: str, data: bytes, *, name: str | None = None) -> dict:
    """Create a new domain from an exported file. Ids are regenerated; refs are dropped
    (the documents they pointed to are not part of the file)."""
    _require_edit(role)
    try:
        doc = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TreeError(400, "This is not a valid tree file.") from exc
    if not isinstance(doc, dict) or doc.get("format") != EXPORT_FORMAT:
        raise TreeError(400, "This file was not exported from a PathMind knowledge tree.")
    items = doc.get("nodes")
    if not isinstance(items, list) or not items:
        raise TreeError(400, "The file contains no nodes.")
    if len(items) > MAX_IMPORT_NODES:
        raise TreeError(400, f"A tree can hold at most {MAX_IMPORT_NODES} nodes.")
    ids = {str(i.get("id")) for i in items if isinstance(i, dict) and i.get("id")}
    domain_info = doc.get("domain") if isinstance(doc.get("domain"), dict) else {}
    domain = _create_domain(
        db, user_id, name or domain_info.get("name") or "Imported tree", str(domain_info.get("description") or "")
    )
    new_id: dict[str, str] = {}
    pending = [i for i in items if isinstance(i, dict) and i.get("id")]
    # Parents first; anything whose parent is missing becomes a top-level topic.
    remaining = pending
    for _ in range(64):
        if not remaining:
            break
        later = []
        for item in remaining:
            pid = item.get("parent_id")
            if pid and str(pid) in ids and str(pid) not in new_id:
                later.append(item)
                continue
            node = KnowledgeNode(
                domain_id=domain.id,
                parent_id=new_id.get(str(pid)) if pid else None,
                title=_clean(item.get("title"), 200, required=True, field="Title"),
                summary=_clean(item.get("summary"), 4000),
                position=int(item.get("position") or 0),
                refs=[],
                updated_by=user_id,
            )
            db.add(node)
            db.flush()
            new_id[str(item["id"])] = node.id
        remaining = later
    audit.record(
        db, user_id, "store.tree.import", target_type="domain", target_id=domain.id,
        data={"nodes": len(new_id), "name": domain.name}, commit=False,
    )
    db.commit()
    return {"domain_id": domain.id, "name": domain.name, "nodes": len(new_id)}
