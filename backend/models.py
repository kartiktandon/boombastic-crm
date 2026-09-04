from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

LeadStatus = Literal["new", "contacted", "interested", "call_back", "meeting_done", "proposal_sent", "on_hold", "not_interested", "won", "lost", "ringing"]
Platform = Literal["facebook", "instagram", "meta", "website", "referral", "event", "outbound", "manual_adding", "other"]

class Note(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Activity(BaseModel):
    type: str
    message: str
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserRegister(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "sales_lead", "sales_rep", "delivery"] = "sales_rep"

class BusinessSettings(BaseModel):
    business_name: str = Field(default="Boombastic", min_length=2, max_length=120)
    business_type: str = Field(default="Entertainment & Events", max_length=120)
    business_email: Optional[str] = Field(default=None, max_length=160)
    business_phone: Optional[str] = Field(default=None, max_length=40)
    website: Optional[str] = Field(default=None, max_length=300)
    address: Optional[str] = Field(default=None, max_length=300)
    timezone: str = Field(default="Asia/Kolkata", max_length=80)
    default_lead_owner: Optional[str] = Field(default=None, max_length=120)
    auto_assign_leads: bool = False
    followup_reminder_minutes: int = Field(default=30, ge=0, le=10080)
    inactivity_days: int = Field(default=7, ge=1, le=365)
    weekday_start: str = "10:00"
    weekday_end: str = "20:00"
    weekend_start: str = "10:00"
    weekend_end: str = "22:00"
    notify_new_leads: bool = True
    notify_followups: bool = True
    notify_bookings: bool = True

class LeadBase(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    company: Optional[str] = Field(default=None, max_length=160)
    email: Optional[str] = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(default=None, max_length=40)
    city: Optional[str] = Field(default=None, max_length=100)
    source: Platform = "website"
    campaign: Optional[str] = Field(default=None, max_length=160)
    service: Optional[str] = Field(default=None, max_length=160)
    budget: Optional[str] = Field(default=None, max_length=80)
    timeline: Optional[str] = Field(default=None, max_length=80)
    status: LeadStatus = "new"
    temperature: Literal["hot", "warm", "cold"] = "warm"
    assigned_to: Optional[str] = Field(default=None, max_length=120)
    next_follow_up: Optional[datetime] = None
    last_follow_up_completed_at: Optional[datetime] = None
    tags: list[str] = Field(default_factory=list)
    project_name: Optional[str] = Field(default=None, max_length=180)
    alternate_phones: list[str] = Field(default_factory=list)
    alternate_contacts: list[str] = Field(default_factory=list)
    closed_amount: Optional[float] = Field(default=None, ge=0)
    gst_rate: float = Field(default=18, ge=0, le=100)

    @model_validator(mode="after")
    def require_contact_method(self):
        if not self.email and not self.phone:
            raise ValueError("Either email or phone is required")
        return self

class LeadCreate(LeadBase): pass

class LeadUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=140)
    company: Optional[str] = Field(default=None, max_length=160)
    email: Optional[str] = Field(default=None, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: Optional[str] = Field(default=None, max_length=40)
    city: Optional[str] = Field(default=None, max_length=100)
    source: Optional[Platform] = None
    campaign: Optional[str] = Field(default=None, max_length=160)
    service: Optional[str] = Field(default=None, max_length=160)
    budget: Optional[str] = Field(default=None, max_length=80)
    timeline: Optional[str] = Field(default=None, max_length=80)
    status: Optional[LeadStatus] = None
    temperature: Optional[Literal["hot", "warm", "cold"]] = None
    assigned_to: Optional[str] = Field(default=None, max_length=120)
    next_follow_up: Optional[datetime] = None
    last_follow_up_completed_at: Optional[datetime] = None
    tags: Optional[list[str]] = None
    closed_amount: Optional[float] = Field(default=None, ge=0)
    project_name: Optional[str] = Field(default=None, max_length=180)
    alternate_phones: Optional[list[str]] = None
    alternate_contacts: Optional[list[str]] = None
    gst_rate: Optional[float] = Field(default=None, ge=0, le=100)

class LeadStatusUpdate(BaseModel): status: LeadStatus

class Meeting(BaseModel):
    lead_id: str
    title: str = Field(min_length=2, max_length=180)
    scheduled_at: datetime
    duration_minutes: int = Field(default=30, ge=15, le=480)
    mode: Literal["online", "offline"] = "online"
    meeting_url: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=300)
    status: Literal["scheduled", "completed", "cancelled"] = "scheduled"
    attendees: list[str] = Field(default_factory=list)
    summary: Optional[str] = Field(default=None, max_length=5000)

class MeetingUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=15, le=480)
    mode: Optional[Literal["online", "offline"]] = None
    meeting_url: Optional[str] = None
    location: Optional[str] = Field(default=None, max_length=300)
    status: Optional[Literal["scheduled", "completed", "cancelled"]] = None
    attendees: Optional[list[str]] = None
    summary: Optional[str] = Field(default=None, max_length=5000)

class LineItem(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    qty: int = Field(default=1, ge=1)
    price: float = Field(default=0, ge=0)

class Proposal(BaseModel):
    lead_id: str
    title: str = Field(min_length=2, max_length=180)
    status: Literal["draft", "sent", "viewed", "accepted", "rejected"] = "draft"
    line_items: list[LineItem] = Field(default_factory=list)
    tax_rate: float = Field(default=18, ge=0, le=100)
    discount: float = Field(default=0, ge=0)
    valid_until: Optional[datetime] = None
    terms: Optional[str] = Field(default=None, max_length=8000)

class ProposalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    status: Optional[Literal["draft", "sent", "viewed", "accepted", "rejected"]] = None
    line_items: Optional[list[LineItem]] = None
    tax_rate: Optional[float] = Field(default=None, ge=0, le=100)
    discount: Optional[float] = Field(default=None, ge=0)
    valid_until: Optional[datetime] = None
    terms: Optional[str] = Field(default=None, max_length=8000)

class Agreement(BaseModel):
    proposal_id: str
    lead_id: str
    title: str = "Service Agreement"
    status: Literal["draft", "sent", "pending", "signed", "void"] = "pending"
    file_url: Optional[str] = None
    valid_until: Optional[datetime] = None

class AgreementUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    status: Optional[Literal["draft", "sent", "pending", "signed", "void"]] = None
    file_url: Optional[str] = None
    valid_until: Optional[datetime] = None

class Project(BaseModel):
    lead_id: str
    agreement_id: Optional[str] = None
    name: str = Field(min_length=2, max_length=180)
    status: Literal["planning", "active", "review", "on_hold", "delivered"] = "planning"
    team: list[str] = Field(default_factory=list)
    monthly_value: float = Field(default=0, ge=0)
    progress: int = Field(default=0, ge=0, le=100)
    due_date: Optional[datetime] = None
    deliverables: list[str] = Field(default_factory=list)

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    status: Optional[Literal["planning", "active", "review", "on_hold", "delivered"]] = None
    team: Optional[list[str]] = None
    monthly_value: Optional[float] = Field(default=None, ge=0)
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    due_date: Optional[datetime] = None
    deliverables: Optional[list[str]] = None
