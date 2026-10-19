"""Knowledge tree API. The main tree is hidden: only R&D and administrators read or change it.

See ``services.knowledge_tree``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pathmind.database.connection import get_db
from pathmind.multi_user.context import get_current_user
from pathmind.services import audit
from pathmind.services import knowledge_tree as kt

router = APIRouter()


def _who():
    u = get_current_user()
    return str(u.id or ""), str(u.username or ""), str(u.role or "user")


def _require_view() -> None:
    _, _, role = _who()
    if not kt.can_edit(role):
        raise HTTPException(status_code=403, detail="The main knowledge tree is only visible to R&D.")


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except kt.TreeError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.message)


class DomainBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""


class DomainPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    kb_name: str | None = None  # "" or null unlinks; omit to leave unchanged


class NodeBody(BaseModel):
    parent_id: str | None = None
    title: str = Field(min_length=1, max_length=200)
    summary: str = ""


class NodePatch(BaseModel):
    title: str | None = None
    summary: str | None = None


class MoveBody(BaseModel):
    parent_id: str | None = None


class AskBody(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    domain_id: str | None = None


@router.get("/me")
def my_rights():
    _, _, role = _who()
    return {"role": role, "can_edit": kt.can_edit(role)}


@router.get("/domains")
def list_domains(db: Session = Depends(get_db)):
    _require_view()
    return {"domains": kt.domain_summaries(db)}


@router.post("/domains")
def add_domain(body: DomainBody, db: Session = Depends(get_db)):
    uid, _, role = _who()
    d = _run(kt.create_domain, db, role, uid, body.name, body.description)
    return {"id": d.id, "slug": d.slug, "name": d.name}


@router.get("/kb-options")
def kb_options():
    """Administrator's GraphRAG knowledge bases a domain can be linked to."""
    _, _, role = _who()
    if not kt.can_edit(role):
        raise HTTPException(status_code=403, detail="Only R&D or administrators can link knowledge bases.")
    return {"knowledge_bases": kt.admin_kb_names()}


@router.patch("/domains/{domain_id}")
def patch_domain(domain_id: str, body: DomainPatch, db: Session = Depends(get_db)):
    _, _, role = _who()
    fields = body.model_dump(exclude_unset=True)
    d = _run(
        kt.update_domain, db, role, domain_id, name=fields.get("name"),
        description=fields.get("description"), kb_name=fields.get("kb_name"), set_kb="kb_name" in fields,
    )
    return {"id": d.id, "name": d.name, "kb_name": d.kb_name}


@router.delete("/domains/{domain_id}")
def remove_domain(domain_id: str, db: Session = Depends(get_db)):
    _, _, role = _who()
    _run(kt.delete_domain, db, role, domain_id)
    return {"ok": True}


@router.get("/domains/{domain_id}/tree")
def get_tree(domain_id: str, db: Session = Depends(get_db)):
    _require_view()
    return _run(kt.tree_of, db, domain_id)


@router.post("/domains/import")
async def import_new_domain(
    file: UploadFile = File(...), name: str = Form(""), db: Session = Depends(get_db)
):
    uid, _, role = _who()
    data = await file.read()
    return _run(
        kt.import_file, db, role, uid, domain_id=None, new_domain_name=name.strip() or None,
        filename=file.filename or "file", data=data,
    )


@router.post("/domains/{domain_id}/import")
async def import_into_domain(
    domain_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    uid, _, role = _who()
    data = await file.read()
    return _run(
        kt.import_file, db, role, uid, domain_id=domain_id, new_domain_name=None,
        filename=file.filename or "file", data=data,
    )


@router.post("/domains/{domain_id}/nodes")
def add_node(domain_id: str, body: NodeBody, db: Session = Depends(get_db)):
    uid, _, role = _who()
    n = _run(kt.create_node, db, role, uid, domain_id, body.parent_id, body.title, body.summary)
    return {"id": n.id}


@router.get("/nodes/{node_id}")
def get_node(node_id: str, db: Session = Depends(get_db)):
    _require_view()
    return _run(kt.node_detail, db, node_id)


@router.patch("/nodes/{node_id}")
def patch_node(node_id: str, body: NodePatch, db: Session = Depends(get_db)):
    uid, _, role = _who()
    n = _run(kt.update_node, db, role, uid, node_id, title=body.title, summary=body.summary)
    return {"id": n.id, "version": n.version}


@router.post("/nodes/{node_id}/move")
def relocate_node(node_id: str, body: MoveBody, db: Session = Depends(get_db)):
    uid, _, role = _who()
    n = _run(kt.move_node, db, role, uid, node_id, body.parent_id)
    return {"id": n.id}


@router.delete("/nodes/{node_id}")
def remove_node(node_id: str, db: Session = Depends(get_db)):
    _, _, role = _who()
    return {"deleted": _run(kt.delete_node, db, role, node_id)}


@router.get("/search")
def search(q: str, db: Session = Depends(get_db)):
    _require_view()
    return {"results": kt.search_nodes(db, q)}


@router.post("/ask")
async def ask(body: AskBody) -> dict[str, Any]:
    """Run the unified tree + GraphRAG retrieval (R&D and administrators: to test the setup)."""
    from pathmind.services.knowledge_tree.unified import knowledge_search

    _, _, role = _who()
    if not kt.can_edit(role):
        raise HTTPException(status_code=403, detail="Only R&D or administrators can test retrieval.")
    try:
        return await knowledge_search(body.query, domain_id=body.domain_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── R&D document store, tree export/import, audit trail ──────────────────

MAX_UPLOAD = 25 * 1024 * 1024


async def _read_limited(file: UploadFile) -> bytes:
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="File is larger than 25 MB.")
    return data


@router.get("/documents")
def list_documents(domain_id: str | None = None, db: Session = Depends(get_db)):
    _, _, role = _who()
    return {"documents": _run(kt.store.list_documents, db, role, domain_id)}


@router.post("/domains/{domain_id}/documents")
async def upload_document(domain_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    uid, _, role = _who()
    data = await _read_limited(file)
    return _run(
        kt.store.upload_document, db, role, uid,
        domain_id=domain_id, filename=file.filename or "file", data=data,
    )


@router.get("/documents/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db)):
    uid, _, role = _who()
    data, ctype, name = _run(kt.store.read_document, db, role, uid, document_id)
    safe = name.replace('"', "")
    return Response(
        content=data, media_type=ctype,
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@router.delete("/documents/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    uid, _, role = _who()
    _run(kt.store.delete_document, db, role, uid, document_id)
    return {"ok": True}


@router.get("/domains/{domain_id}/export")
def export_tree(domain_id: str, db: Session = Depends(get_db)):
    uid, _, role = _who()
    return _run(kt.store.export_tree, db, role, uid, domain_id)


@router.post("/domains/import-tree")
async def import_tree(file: UploadFile = File(...), name: str = Form(""), db: Session = Depends(get_db)):
    uid, _, role = _who()
    data = await _read_limited(file)
    return _run(kt.store.import_tree, db, role, uid, data, name=name.strip() or None)


@router.get("/audit")
def audit_log(action_prefix: str = "", limit: int = 100, db: Session = Depends(get_db)):
    _require_view()
    return {"entries": audit.list_recent(db, limit=max(1, min(limit, 500)), action_prefix=action_prefix)}
