from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal

# --- AUTH & USER ---
class UserBase(BaseModel):
    username: str
    role: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str
    user_id: int
    profile_id: Optional[int] = None # student_id or warden_id
    name: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


# --- WARDEN ---
class WardenBase(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None

class WardenResponse(WardenBase):
    warden_id: int
    user_id: int

    class Config:
        from_attributes = True


# --- HOSTEL ---
class HostelBase(BaseModel):
    hostel_name: str
    hostel_type: str
    capacity: int
    warden_id: Optional[int] = None

class HostelCreate(HostelBase):
    pass

class HostelResponse(HostelBase):
    hostel_id: int
    warden_name: Optional[str] = None

    class Config:
        from_attributes = True


# --- ROOM ---
class RoomBase(BaseModel):
    hostel_id: int
    room_number: str
    floor: int
    room_type: str
    capacity: int

class RoomCreate(RoomBase):
    pass

class RoomResponse(RoomBase):
    room_id: int
    occupied_count: int
    status: str
    hostel_name: Optional[str] = None

    class Config:
        from_attributes = True


# --- STUDENT ---
class StudentBase(BaseModel):
    roll_no: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    department: Optional[str] = None
    year: Optional[int] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None

class StudentCreate(StudentBase):
    username: str
    password: str

class StudentUpdate(BaseModel):
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None

class StudentResponse(StudentBase):
    student_id: int
    user_id: int
    admission_date: date
    status: str
    room_number: Optional[str] = None
    hostel_name: Optional[str] = None

    class Config:
        from_attributes = True


# --- ROOM ALLOCATION ---
class RoomAllocationCreate(BaseModel):
    student_id: int
    room_id: int

class RoomAllocationResponse(BaseModel):
    allocation_id: int
    student_id: int
    student_name: str
    roll_no: str
    room_id: int
    room_number: str
    hostel_name: str
    allocation_date: date
    vacated_date: Optional[date] = None
    status: str

    class Config:
        from_attributes = True


# --- FEE & PAYMENTS ---
class FeeStructureBase(BaseModel):
    room_type: str
    academic_fee: Decimal
    mess_fee: Decimal
    caution_deposit: Decimal

class FeeStructureResponse(FeeStructureBase):
    fee_structure_id: int

    class Config:
        from_attributes = True

class StudentFeeResponse(BaseModel):
    fee_id: int
    student_id: int
    student_name: str
    roll_no: str
    room_type: str
    amount_due: Decimal
    amount_paid: Decimal
    due_date: date
    status: str

    class Config:
        from_attributes = True

class PaymentCreate(BaseModel):
    fee_id: int
    amount: Decimal
    payment_method: str # UPI, CARD, NET_BANKING, CASH
    transaction_id: str

class PaymentResponse(BaseModel):
    payment_id: int
    student_id: int
    student_name: str
    fee_id: int
    amount: Decimal
    payment_date: datetime
    payment_method: str
    transaction_id: str
    status: str

    class Config:
        from_attributes = True


# --- COMPLAINTS ---
class ComplaintCreate(BaseModel):
    category: str
    description: str
    priority: Optional[str] = "MEDIUM"

class ComplaintUpdate(BaseModel):
    status: str # ASSIGNED, IN_PROGRESS, RESOLVED
    assigned_to: Optional[int] = None
    resolution: Optional[str] = None

class ComplaintResponse(BaseModel):
    complaint_id: int
    student_id: int
    student_name: str
    roll_no: str
    room_number: Optional[str] = None
    category: str
    description: str
    priority: str
    created_at: datetime
    assigned_to: Optional[int] = None
    assigned_warden_name: Optional[str] = None
    status: str
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None

    class Config:
        from_attributes = True


# --- VISITORS ---
class VisitorCreate(BaseModel):
    student_id: int
    visitor_name: str
    relationship: str
    phone: Optional[str] = None

class VisitorUpdate(BaseModel):
    status: str # CHECKED_OUT, DENIED
    exit_time: Optional[datetime] = None

class VisitorResponse(BaseModel):
    visitor_id: int
    student_id: int
    student_name: str
    roll_no: str
    visitor_name: str
    relationship: str
    phone: Optional[str] = None
    visit_date: date
    entry_time: datetime
    exit_time: Optional[datetime] = None
    approved_by: Optional[int] = None
    status: str

    class Config:
        from_attributes = True


# --- LEAVE REQUESTS ---
class LeaveRequestCreate(BaseModel):
    pass_type: Optional[str] = "LEAVE" # LEAVE, HOME_PASS, OUT_PASS
    from_date: date
    to_date: date
    reason: str
    destination: str
    emergency_contact: str

class LeaveRequestUpdate(BaseModel):
    status: str # APPROVED, REJECTED
    action_by: int

class LeaveRequestResponse(BaseModel):
    leave_id: int
    student_id: int
    student_name: str
    roll_no: str
    pass_type: str
    from_date: date
    to_date: date
    reason: str
    destination: str
    emergency_contact: str
    status: str
    action_by: Optional[int] = None
    action_date: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- ROOM CHANGE REQUESTS ---
class RoomChangeRequestCreate(BaseModel):
    requested_room_id: int
    reason: str

class RoomChangeRequestUpdate(BaseModel):
    status: str # APPROVED, REJECTED

class RoomChangeRequestResponse(BaseModel):
    request_id: int
    student_id: int
    student_name: str
    roll_no: str
    current_room_id: int
    current_room_number: str
    requested_room_id: int
    requested_room_number: str
    reason: str
    status: str
    action_by: Optional[int] = None
    action_date: Optional[datetime] = None

    class Config:
        from_attributes = True


# --- ATTENDANCE ---
class AttendanceCreate(BaseModel):
    student_id: int
    status: str # PRESENT, ABSENT, LEAVE

class AttendanceBulkCreate(BaseModel):
    date: date
    records: List[AttendanceCreate]

class AttendanceResponse(BaseModel):
    attendance_id: int
    student_id: int
    student_name: str
    roll_no: str
    date: date
    status: str
    marked_by: Optional[int] = None

    class Config:
        from_attributes = True


# --- NOTICE BOARD ---
class NoticeCreate(BaseModel):
    title: str
    description: str
    audience: Optional[str] = "ALL" # ALL, STUDENTS, WARDENS, STAFF
    expiry_date: Optional[date] = None

class NoticeResponse(NoticeCreate):
    notice_id: int
    created_at: datetime
    created_by: Optional[int] = None
    author_name: Optional[str] = None

    class Config:
        from_attributes = True


# --- INVENTORY ---
class InventoryResponse(BaseModel):
    item_id: int
    hostel_id: int
    hostel_name: str
    item_name: str
    total_qty: int
    occupied_qty: int
    damaged_qty: int
    available_qty: int

    class Config:
        from_attributes = True

class InventoryTransactionCreate(BaseModel):
    item_id: int
    transaction_type: str # ADD, REMOVE, DAMAGE_REPORT, REPAIR_REPORT
    quantity: int
    remarks: Optional[str] = None


# --- MESS MENU & FEEDBACK ---
class MessMenuResponse(BaseModel):
    menu_id: int
    hostel_id: int
    hostel_name: str
    day_of_week: str
    breakfast: str
    lunch: str
    dinner: str

    class Config:
        from_attributes = True

class MessFeedbackCreate(BaseModel):
    food_quality: int
    taste: int
    cleanliness: int
    comments: Optional[str] = None

class MessFeedbackResponse(BaseModel):
    feedback_id: int
    student_id: int
    student_name: str
    date: date
    food_quality: int
    taste: int
    cleanliness: int
    comments: Optional[str] = None

    class Config:
        from_attributes = True
