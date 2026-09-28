"""SQLAlchemy ORM models for Users, Plans, Subscriptions, Payments, Quotas, and Friends."""

from datetime import datetime
import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from pathmind.database.connection import Base


def _gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    email = Column(String(255), unique=True, index=True, nullable=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)  # "admin" | "user"
    avatar = Column(String(255), default="")
    timezone = Column(String(50), default="UTC")
    locale = Column(String(20), default="vi-VN")
    is_active = Column(Boolean, default=True)
    # Registration profile (mirrors the identity store, see services/auth).
    full_name = Column(String(120), nullable=True)
    email_verified = Column(Boolean, nullable=True, default=False)
    email_verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id = Column(String(50), primary_key=True)  # "free" | "pro" | "enterprise"
    name = Column(String(100), nullable=False)
    price_monthly = Column(Float, default=0.0)
    price_yearly = Column(Float, default=0.0)
    max_tokens_per_day = Column(BigInteger, default=50000)
    max_tokens_per_month = Column(BigInteger, default=1500000)
    max_storage_bytes = Column(BigInteger, default=200 * 1024 * 1024)  # 200 MB
    max_upload_file_size_bytes = Column(BigInteger, default=10 * 1024 * 1024)  # 10 MB
    allowed_models = Column(JSON, default=list)  # e.g. ["gemini-1.5-flash", "gpt-4o-mini"]
    allow_custom_api_key = Column(Boolean, default=False)
    # Model used when a user of this plan has not picked one (must be in
    # allowed_models). NULL/"" = the deployment's default model.
    default_model = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True)
    # Marketing copy shown on /pricing. ``features`` empty → generated from limits.
    description = Column(String(500), nullable=True)
    features = Column(JSON, nullable=True)
    sort_order = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, nullable=True, default=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(String(50), ForeignKey("subscription_plans.id"), nullable=False)
    # "active" | "canceled" | "expired" | "replaced"
    status = Column(String(30), default="active", index=True)
    current_period_start = Column(DateTime, default=datetime.utcnow)
    # NULL = never expires (free plan, or an open-ended admin grant)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)
    # Transaction id of the payment that activated/renewed this subscription
    external_subscription_id = Column(String(255), nullable=True)
    billing_interval = Column(String(10), nullable=True, default="monthly")  # "monthly" | "yearly"
    source = Column(String(30), nullable=True, default="system")  # "register" | "payment" | "admin" | "system"
    created_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    canceled_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="subscriptions")
    plan = relationship("SubscriptionPlan", back_populates="subscriptions")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(String(50), ForeignKey("subscription_plans.id"), nullable=False)
    amount = Column(Float, nullable=False)  # always stored in USD
    currency = Column(String(10), default="USD")
    # "vnpay" | "admin" (older rows: "bank_transfer", "stripe", "crypto")
    payment_method = Column(String(50), default="bank_transfer")
    transaction_id = Column(String(255), nullable=True, unique=True)
    # "pending" | "completed" | "failed" | "canceled" | "expired" | "refunded"
    status = Column(String(30), default="pending", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    billing_interval = Column(String(10), nullable=True, default="monthly")
    amount_vnd = Column(BigInteger, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)
    confirmed_by = Column(String(100), nullable=True)
    note = Column(String(500), nullable=True)
    # Gateway transaction id (e.g. ``vnpay:<vnp_TransactionNo>``), for reconciliation.
    gateway_reference = Column(String(255), nullable=True)

    user = relationship("User", back_populates="payments")
    plan = relationship("SubscriptionPlan")


class UsageLog(Base):
    __tablename__ = "usage_logs"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_usage_log_day"),)

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # "YYYY-MM-DD"
    prompt_tokens = Column(BigInteger, default=0)
    completion_tokens = Column(BigInteger, default=0)
    total_tokens = Column(BigInteger, default=0)
    current_storage_bytes = Column(BigInteger, default=0)
    # Quota is enforced on *credits* (cost-weighted tokens, see quota_service).
    # NULL on rows written before credits existed → fall back to total_tokens.
    credits_used = Column(BigInteger, nullable=True, default=0)
    cost_usd = Column(Float, nullable=True, default=0.0)  # real API cost we paid
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="usage_logs")


class UsageModelLog(Base):
    """Per user / day / model breakdown — used for cost & margin reporting."""

    __tablename__ = "usage_model_logs"
    __table_args__ = (UniqueConstraint("user_id", "date", "model", name="uq_usage_model_day"),)

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String(10), nullable=False, index=True)  # "YYYY-MM-DD" (UTC)
    model = Column(String(120), nullable=False)
    price_id = Column(String(80), nullable=True)
    calls = Column(Integer, default=0)
    prompt_tokens = Column(BigInteger, default=0)
    cached_tokens = Column(BigInteger, default=0)
    completion_tokens = Column(BigInteger, default=0)
    credits_used = Column(BigInteger, default=0)
    cost_usd = Column(Float, default=0.0)


class ModelPrice(Base):
    """API list price of an LLM, used to turn tokens into cost and credits.

    ``id`` is the canonical model id (without provider prefix such as
    ``models/``). ``aliases`` lists other names that map to the same price.
    Lookup is exact-or-alias first, then the longest id that the requested
    model name starts with (``gemini-3.1-flash-lite-preview`` →
    ``gemini-3.1-flash-lite``). The row with id ``*`` is the fallback for
    unknown models and should be priced conservatively.
    """

    __tablename__ = "model_prices"

    id = Column(String(80), primary_key=True)
    display_name = Column(String(120), nullable=True)
    provider = Column(String(40), nullable=True)
    input_per_m = Column(Float, nullable=False, default=0.0)  # USD / 1M input tokens
    cached_input_per_m = Column(Float, nullable=True)  # NULL → 25% of input price
    output_per_m = Column(Float, nullable=False, default=0.0)  # USD / 1M output tokens
    aliases = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=True, default=True)
    notes = Column(String(300), nullable=True)
    updated_at = Column(DateTime, nullable=True, default=datetime.utcnow, onupdate=datetime.utcnow)


class Friendship(Base):
    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("user_id", "friend_id", name="uq_friendship_pair"),)

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default="pending")  # "pending" | "accepted" | "rejected" | "blocked"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PartnerShare(Base):
    __tablename__ = "partner_shares"
    __table_args__ = (
        UniqueConstraint("partner_id", "shared_with_id", name="uq_partner_share_target"),
    )

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    partner_id = Column(String(100), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    shared_with_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(20), default="use")  # "use" | "clone" | "collaborate"
    created_at = Column(DateTime, default=datetime.utcnow)


class SharedRoom(Base):
    __tablename__ = "shared_rooms"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    room_code = Column(String(50), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    host_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    partner_id = Column(String(100), nullable=True)
    discussion_mode = Column(String(50), default="round_robin")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("RoomMember", back_populates="room", cascade="all, delete-orphan")


class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_member"),)

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    room_id = Column(String(36), ForeignKey("shared_rooms.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), default="participant")  # "host" | "participant"
    joined_at = Column(DateTime, default=datetime.utcnow)

    room = relationship("SharedRoom", back_populates="members")


class RoomMessage(Base):
    """One line of a study room's shared chat (a member, the room's Partner, or a system note)."""

    __tablename__ = "room_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)  # monotonic → ``?after=`` polling
    room_id = Column(String(36), ForeignKey("shared_rooms.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=True)  # None for partner / system lines
    role = Column(String(20), nullable=False, default="user")  # "user" | "partner" | "system"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailVerification(Base):
    """One-time 6-digit code sent to confirm a user's email address."""

    __tablename__ = "email_verifications"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    user_id = Column(String(36), nullable=False, index=True)  # identity-store id
    email = Column(String(255), nullable=False, index=True)
    code_hash = Column(String(128), nullable=False)
    attempts = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Community: shared skill hub + forum (api/routers/community.py)
# ---------------------------------------------------------------------------


class CommunitySkill(Base):
    """A skill package a user shared with everyone (``SKILL.md`` + text support files)."""

    __tablename__ = "community_skills"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    slug = Column(String(64), unique=True, index=True, nullable=False)
    title = Column(String(120), nullable=False)
    description = Column(String(500), nullable=False, default="")
    category = Column(String(40), nullable=False, default="other", index=True)
    tags = Column(JSON, default=list)
    content = Column(Text, nullable=False)  # full SKILL.md (frontmatter + body)
    files = Column(JSON, default=dict)  # {"references/x.md": "text", ...}
    author_id = Column(String(36), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    install_count = Column(Integer, nullable=False, default=0)
    like_count = Column(Integer, nullable=False, default=0)
    is_hidden = Column(Boolean, nullable=False, default=False)  # removed by a moderator
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class CommunitySkillInstall(Base):
    """One row per (skill, user) so ``install_count`` counts people, not clicks."""

    __tablename__ = "community_skill_installs"
    __table_args__ = (UniqueConstraint("skill_id", "user_id", name="uq_community_install"),)

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    skill_id = Column(String(36), ForeignKey("community_skills.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ForumPost(Base):
    __tablename__ = "forum_posts"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    author_id = Column(String(36), nullable=False, index=True)
    category = Column(String(40), nullable=False, default="general", index=True)
    title = Column(String(300), nullable=False)
    body = Column(Text, nullable=False, default="")
    skill_id = Column(String(36), nullable=True)  # optional linked community skill
    score = Column(Integer, nullable=False, default=0)
    comment_count = Column(Integer, nullable=False, default=0)
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_locked = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)


class ForumComment(Base):
    __tablename__ = "forum_comments"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    post_id = Column(String(36), ForeignKey("forum_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(String(36), nullable=True)
    author_id = Column(String(36), nullable=False)
    body = Column(Text, nullable=False)
    score = Column(Integer, nullable=False, default=0)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)


class CommunityVote(Base):
    """Votes on posts / comments (±1) and likes on skills (+1)."""

    __tablename__ = "community_votes"
    __table_args__ = (
        UniqueConstraint("target_type", "target_id", "user_id", name="uq_community_vote"),
    )

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    target_type = Column(String(16), nullable=False)  # "post" | "comment" | "skill"
    target_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    value = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class CommunityReport(Base):
    """A user flagging a post / comment / skill for moderators."""

    __tablename__ = "community_reports"
    __table_args__ = (
        UniqueConstraint("target_type", "target_id", "reporter_id", name="uq_community_report"),
    )

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    target_type = Column(String(16), nullable=False)  # "post" | "comment" | "skill"
    target_id = Column(String(36), nullable=False, index=True)
    reporter_id = Column(String(36), nullable=False)
    reason = Column(String(32), nullable=False, default="other")
    details = Column(String(500), nullable=False, default="")
    status = Column(String(16), nullable=False, default="open", index=True)  # open | dismissed | removed
    resolved_by = Column(String(36), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CommunityNotification(Base):
    """In-app notice: a reply to my post/comment, my skill added, my content removed."""

    __tablename__ = "community_notifications"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    user_id = Column(String(36), nullable=False, index=True)  # recipient
    kind = Column(String(32), nullable=False)
    actor_id = Column(String(36), nullable=True)
    post_id = Column(String(36), nullable=True)
    comment_id = Column(String(36), nullable=True)
    skill_id = Column(String(36), nullable=True)
    preview = Column(String(300), nullable=False, default="")
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
