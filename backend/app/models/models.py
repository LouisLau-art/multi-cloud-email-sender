from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from ..core.database import Base


class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    # Aliyun
    access_key_id = Column(String)
    access_key_secret = Column(String)
    region_id = Column(String, default="cn-hangzhou")
    # Tencent
    tencent_secret_id = Column(String)
    tencent_secret_key = Column(String)
    tencent_region = Column(String, default="ap-hongkong")

    # Tracking
    track_domain = Column(
        String, default="http://192.168.2.8:8000"
    )  # Base URL for pixel/links

    from_alias = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SavedReplyTo(Base):
    """存储用户常用的回信地址"""

    __tablename__ = "saved_reply_tos"
    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ContactList(Base):
    __tablename__ = "contact_lists"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    total_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    contacts = relationship(
        "Contact", back_populates="contact_list", cascade="all, delete-orphan"
    )


class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    name = Column(String)
    extra_vars = Column(Text)  # JSON string for other variables
    list_id = Column(Integer, ForeignKey("contact_lists.id"))
    contact_list = relationship("ContactList", back_populates="contacts")


class EmailTemplate(Base):
    __tablename__ = "templates"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)  # Template name for our UI
    subject = Column(String)  # Supports ${name}
    body = Column(Text)  # Supports ${name}
    from_alias = Column(String)  # Sender Name (e.g. "Marketing Team")

    # Template isolation
    provider = Column(String, default="local")  # 'aliyun', 'tencent', 'local'
    provider_id = Column(
        String, nullable=True
    )  # Cloud Template ID (e.g. 12345 or 'template_abc')

    created_at = Column(DateTime, default=datetime.utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    provider = Column(String, default="aliyun")  # 'aliyun' or 'tencent'
    template_id = Column(Integer, ForeignKey("templates.id"))
    list_id = Column(Integer, ForeignKey("contact_lists.id"))
    account_name = Column(String)  # Aliyun sender address
    tag_name = Column(String)

    # Task-specific override
    from_alias = Column(String, nullable=True)
    reply_to_address = Column(String, nullable=True)

    # Tracking Options
    track_opens = Column(Boolean, default=True)
    track_clicks = Column(Boolean, default=True)

    status = Column(
        String, default="pending"
    )  # pending, sending, completed, paused, error, scheduled
    total_recipients = Column(Integer)
    sent_count = Column(Integer, default=0)

    batch_size = Column(Integer, default=2000)
    interval_minutes = Column(Integer, default=15)

    scheduled_start_time = Column(DateTime, nullable=True)  # Planned start time

    scheduled_at = Column(
        DateTime, default=datetime.utcnow
    )  # When it was created/scheduled
    created_at = Column(DateTime, default=datetime.utcnow)

    batches = relationship("CampaignBatch", back_populates="campaign")


class CampaignBatch(Base):
    __tablename__ = "campaign_batches"
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    status = Column(String)  # pending, sent, error
    recipient_count = Column(Integer)
    error_message = Column(Text)
    sent_at = Column(DateTime)

    campaign = relationship("Campaign", back_populates="batches")


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipients"
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=True)
    email = Column(String, index=True)
    status = Column(
        String, default="sent"
    )  # sent, failed, opened, clicked, unsubscribed

    error_message = Column(Text, nullable=True)

    sent_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)

    # Unique ID for tracking pixel/links (e.g. UUID)
    tracking_id = Column(String, unique=True, index=True)

    # Cloud provider message ID (for Pull Tracking)
    message_id = Column(String, nullable=True, index=True)  # e.g. Tencent's MessageId
    provider = Column(
        String, nullable=True
    )  # 'aliyun' or 'tencent' - for tracking lookup

    campaign = relationship("Campaign", back_populates="recipients")
    tracked_links = relationship(
        "CampaignRecipientLink", back_populates="recipient", cascade="all, delete-orphan"
    )


class CampaignRecipientLink(Base):
    __tablename__ = "campaign_recipient_links"
    __table_args__ = (
        UniqueConstraint(
            "tracking_id", "target_url", name="uq_campaign_recipient_link_target"
        ),
    )
    id = Column(Integer, primary_key=True, index=True)
    tracking_id = Column(
        String, ForeignKey("campaign_recipients.tracking_id"), nullable=False, index=True
    )
    target_url = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    recipient = relationship("CampaignRecipient", back_populates="tracked_links")


# Update Campaign relationship
Campaign.recipients = relationship(
    "CampaignRecipient", back_populates="campaign", cascade="all, delete-orphan"
)
