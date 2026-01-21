from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
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
    tencent_region = Column(String, default="ap-guangzhou")
    
    from_alias = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ContactList(Base):
    __tablename__ = "contact_lists"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    total_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    contacts = relationship("Contact", back_populates="contact_list", cascade="all, delete-orphan")

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
    subject = Column(String) # Supports ${name}
    body = Column(Text)      # Supports ${name}
    from_alias = Column(String) # Sender Name (e.g. "Marketing Team")
    created_at = Column(DateTime, default=datetime.utcnow)

class Campaign(Base):
    __tablename__ = "campaigns"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    provider = Column(String, default="aliyun") # 'aliyun' or 'tencent'
    template_id = Column(Integer, ForeignKey("templates.id"))
    list_id = Column(Integer, ForeignKey("contact_lists.id"))
    account_name = Column(String) # Aliyun sender address
    tag_name = Column(String)
    
    # Task-specific override
    from_alias = Column(String, nullable=True) 
    
    status = Column(String, default="pending") # pending, sending, completed, paused, error, scheduled
    total_recipients = Column(Integer)
    sent_count = Column(Integer, default=0)
    
    batch_size = Column(Integer, default=2000)
    interval_minutes = Column(Integer, default=15)
    
    scheduled_start_time = Column(DateTime, nullable=True) # Planned start time
    
    scheduled_at = Column(DateTime, default=datetime.utcnow) # When it was created/scheduled
    created_at = Column(DateTime, default=datetime.utcnow)
    
    batches = relationship("CampaignBatch", back_populates="campaign")

class CampaignBatch(Base):
    __tablename__ = "campaign_batches"
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    status = Column(String) # pending, sent, error
    recipient_count = Column(Integer)
    error_message = Column(Text)
    sent_at = Column(DateTime)
    
    campaign = relationship("Campaign", back_populates="batches")
