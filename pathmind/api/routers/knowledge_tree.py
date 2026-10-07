"""Knowledge tree API. Everyone signed in reads; only administrators change it.

See ``services.knowledge_tree``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pathmind.database.connection import get_db
from pathmind.multi_user.context import get_current_user
from pathmind.services import knowledge_tree as kt

router = APIRouter()


def _who():
    u = get_current_user()
    return str(u.id or ""), str(u.username or ""), str(u.role or "user")


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
        raise HTTPException(status_code=403, detail="Only administrators can link knowledge bases.")
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
    return {"results": kt.search_nodes(db, q)}


@router.post("/ask")
async def ask(body: AskBody) -> dict[str, Any]:
    """Run the unified tree + GraphRAG retrieval (administrators: to test the setup)."""
    from pathmind.services.knowledge_tree.unified import knowledge_search

    _, _, role = _who()
    if not kt.can_edit(role):
        raise HTTPException(status_code=403, detail="Only administrators can test retrieval.")
    try:
        return await knowledge_search(body.query, domain_id=body.domain_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
