from sqlalchemy import Column, Integer, String, Numeric, DateTime, Date, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship as orm_relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False) # ADMIN, WARDEN, STUDENT, ACCOUNTANT
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    student_profile = orm_relationship("Student", back_populates="user", uselist=False)
    warden_profile = orm_relationship("Warden", back_populates="user", uselist=False)


class Warden(Base):
    __tablename__ = "warden"

    warden_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(15))
    created_at = Column(DateTime, server_default=func.now())

    user = orm_relationship("User", back_populates="warden_profile")
    hostels = orm_relationship("Hostel", back_populates="warden")
    complaints = orm_relationship("Complaint", back_populates="warden")
    visitors = orm_relationship("Visitor", back_populates="warden")
    leaves = orm_relationship("LeaveRequest", back_populates="warden")
    room_changes = orm_relationship("RoomChangeRequest", back_populates="warden")
    marked_attendance = orm_relationship("Attendance", back_populates="warden")


class Hostel(Base):
    __tablename__ = "hostel"

    hostel_id = Column(Integer, primary_key=True, index=True)
    hostel_name = Column(String(100), unique=True, nullable=False)
    hostel_type = Column(String(20)) # BOYS, GIRLS, COED
    capacity = Column(Integer, nullable=False)
    warden_id = Column(Integer, ForeignKey("warden.warden_id", ondelete="SET NULL"))

    warden = orm_relationship("Warden", back_populates="hostels")
    rooms = orm_relationship("Room", back_populates="hostel", cascade="all, delete-orphan")
    inventory = orm_relationship("Inventory", back_populates="hostel", cascade="all, delete-orphan")
    mess_menus = orm_relationship("MessMenu", back_populates="hostel", cascade="all, delete-orphan")


class Room(Base):
    __tablename__ = "room"

    room_id = Column(Integer, primary_key=True, index=True)
    hostel_id = Column(Integer, ForeignKey("hostel.hostel_id", ondelete="CASCADE"), nullable=False)
    room_number = Column(String(20), nullable=False)
    floor = Column(Integer, nullable=False)
    room_type = Column(String(30), nullable=False) # SINGLE, DOUBLE, TRIPLE, COMMON
    capacity = Column(Integer, nullable=False)
    occupied_count = Column(Integer, default=0)
    status = Column(String(20), default="AVAILABLE") # AVAILABLE, FULL, MAINTENANCE

    __table_args__ = (UniqueConstraint("hostel_id", "room_number", name="uq_hostel_room"),)

    hostel = orm_relationship("Hostel", back_populates="rooms")
    allocations = orm_relationship("RoomAllocation", back_populates="room", cascade="all, delete-orphan")


class Student(Base):
    __tablename__ = "student"

    student_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    roll_no = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    phone = Column(String(15))
    department = Column(String(100))
    year = Column(Integer)
    gender = Column(String(20))
    date_of_birth = Column(Date)
    admission_date = Column(Date, server_default=func.current_date())
    status = Column(String(20), default="ACTIVE") # ACTIVE, GRADUATED, SUSPENDED, LEFT

    user = orm_relationship("User", back_populates="student_profile")
    allocations = orm_relationship("RoomAllocation", back_populates="student", cascade="all, delete-orphan")
    fees = orm_relationship("StudentFee", back_populates="student", cascade="all, delete-orphan")
    payments = orm_relationship("Payment", back_populates="student", cascade="all, delete-orphan")
    complaints = orm_relationship("Complaint", back_populates="student", cascade="all, delete-orphan")
    visitors = orm_relationship("Visitor", back_populates="student", cascade="all, delete-orphan")
    leaves = orm_relationship("LeaveRequest", back_populates="student", cascade="all, delete-orphan")
    room_changes = orm_relationship("RoomChangeRequest", back_populates="student", cascade="all, delete-orphan")
    attendance_records = orm_relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    feedback = orm_relationship("MessFeedback", back_populates="student", cascade="all, delete-orphan")


class RoomAllocation(Base):
    __tablename__ = "room_allocation"

    allocation_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    room_id = Column(Integer, ForeignKey("room.room_id", ondelete="CASCADE"), nullable=False)
    allocation_date = Column(Date, server_default=func.current_date(), nullable=False)
    vacated_date = Column(Date)
    status = Column(String(20), default="ACTIVE") # ACTIVE, COMPLETED, CANCELLED

    student = orm_relationship("Student", back_populates="allocations")
    room = orm_relationship("Room", back_populates="allocations")


class FeeStructure(Base):
    __tablename__ = "fee_structure"

    fee_structure_id = Column(Integer, primary_key=True, index=True)
    room_type = Column(String(30), unique=True, nullable=False)
    academic_fee = Column(Numeric(10, 2), nullable=False)
    mess_fee = Column(Numeric(10, 2), nullable=False)
    caution_deposit = Column(Numeric(10, 2), nullable=False)

    student_fees = orm_relationship("StudentFee", back_populates="fee_structure")


class StudentFee(Base):
    __tablename__ = "student_fee"

    fee_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    fee_structure_id = Column(Integer, ForeignKey("fee_structure.fee_structure_id", ondelete="RESTRICT"), nullable=False)
    amount_due = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), default=0.00)
    due_date = Column(Date, nullable=False)
    status = Column(String(20), default="PENDING") # PENDING, PARTIAL, PAID

    student = orm_relationship("Student", back_populates="fees")
    fee_structure = orm_relationship("FeeStructure", back_populates="student_fees")
    payments = orm_relationship("Payment", back_populates="student_fee", cascade="all, delete-orphan")


class Payment(Base):
    __tablename__ = "payment"

    payment_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    fee_id = Column(Integer, ForeignKey("student_fee.fee_id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    payment_date = Column(DateTime, server_default=func.now())
    payment_method = Column(String(30), nullable=False) # UPI, CARD, NET_BANKING, CASH
    transaction_id = Column(String(100), unique=True, nullable=False)
    status = Column(String(20), default="SUCCESS") # SUCCESS, PENDING, FAILED

    student = orm_relationship("Student", back_populates="payments")
    student_fee = orm_relationship("StudentFee", back_populates="payments")


class Complaint(Base):
    __tablename__ = "complaint"

    complaint_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    category = Column(String(30), nullable=False) # ELECTRICAL, PLUMBING, WIFI, CLEANING, FURNITURE, FOOD, SECURITY, OTHER
    description = Column(Text, nullable=False)
    priority = Column(String(20), default="MEDIUM") # LOW, MEDIUM, HIGH
    created_at = Column(DateTime, server_default=func.now())
    assigned_to = Column(Integer, ForeignKey("warden.warden_id", ondelete="SET NULL"))
    status = Column(String(20), default="NEW") # NEW, ASSIGNED, IN_PROGRESS, RESOLVED
    resolved_at = Column(DateTime)
    resolution = Column(Text)

    student = orm_relationship("Student", back_populates="complaints")
    warden = orm_relationship("Warden", back_populates="complaints")


class Visitor(Base):
    __tablename__ = "visitor"

    visitor_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    visitor_name = Column(String(100), nullable=False)
    relationship = Column(String(50), nullable=False)
    phone = Column(String(15))
    visit_date = Column(Date, server_default=func.current_date())
    entry_time = Column(DateTime, server_default=func.now())
    exit_time = Column(DateTime)
    approved_by = Column(Integer, ForeignKey("warden.warden_id", ondelete="SET NULL"))
    status = Column(String(20), default="APPROVED") # APPROVED, CHECKED_OUT, DENIED

    student = orm_relationship("Student", back_populates="visitors")
    warden = orm_relationship("Warden", back_populates="visitors")


class LeaveRequest(Base):
    __tablename__ = "leave_request"

    leave_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    pass_type = Column(String(20), default="LEAVE") # LEAVE, HOME_PASS, OUT_PASS
    from_date = Column(Date, nullable=False)
    to_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=False)
    destination = Column(Text, nullable=False)
    emergency_contact = Column(String(15), nullable=False)
    status = Column(String(20), default="PENDING") # PENDING, APPROVED, REJECTED
    action_by = Column(Integer, ForeignKey("warden.warden_id", ondelete="SET NULL"))
    action_date = Column(DateTime)

    student = orm_relationship("Student", back_populates="leaves")
    warden = orm_relationship("Warden", back_populates="leaves")


class RoomChangeRequest(Base):
    __tablename__ = "room_change_request"

    request_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    current_room_id = Column(Integer, ForeignKey("room.room_id", ondelete="CASCADE"), nullable=False)
    requested_room_id = Column(Integer, ForeignKey("room.room_id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), default="PENDING") # PENDING, APPROVED, REJECTED
    action_by = Column(Integer, ForeignKey("warden.warden_id", ondelete="SET NULL"))
    action_date = Column(DateTime)

    student = orm_relationship("Student", back_populates="room_changes")
    current_room = orm_relationship("Room", foreign_keys=[current_room_id])
    requested_room = orm_relationship("Room", foreign_keys=[requested_room_id])
    warden = orm_relationship("Warden", back_populates="room_changes")


class Attendance(Base):
    __tablename__ = "attendance"

    attendance_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, server_default=func.current_date(), nullable=False)
    status = Column(String(20), nullable=False) # PRESENT, ABSENT, LEAVE
    marked_by = Column(Integer, ForeignKey("warden.warden_id", ondelete="SET NULL"))

    student = orm_relationship("Student", back_populates="attendance_records")
    warden = orm_relationship("Warden", back_populates="marked_attendance")


class Notice(Base):
    __tablename__ = "notice"

    notice_id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    audience = Column(String(30), default="ALL") # ALL, STUDENTS, WARDENS, STAFF
    expiry_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"))

    author = orm_relationship("User")


class Inventory(Base):
    __tablename__ = "inventory"

    item_id = Column(Integer, primary_key=True, index=True)
    hostel_id = Column(Integer, ForeignKey("hostel.hostel_id", ondelete="CASCADE"), nullable=False)
    item_name = Column(String(100), nullable=False)
    total_qty = Column(Integer, nullable=False)
    occupied_qty = Column(Integer, default=0)
    damaged_qty = Column(Integer, default=0)

    hostel = orm_relationship("Hostel", back_populates="inventory")
    transactions = orm_relationship("InventoryTransaction", back_populates="item", cascade="all, delete-orphan")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transaction"

    transaction_id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("inventory.item_id", ondelete="CASCADE"), nullable=False)
    transaction_type = Column(String(20), nullable=False) # ADD, REMOVE, DAMAGE_REPORT, REPAIR_REPORT
    quantity = Column(Integer, nullable=False)
    remarks = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    item = orm_relationship("Inventory", back_populates="transactions")


class MessMenu(Base):
    __tablename__ = "mess_menu"

    menu_id = Column(Integer, primary_key=True, index=True)
    hostel_id = Column(Integer, ForeignKey("hostel.hostel_id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(String(15), nullable=False) # Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday
    breakfast = Column(Text, nullable=False)
    lunch = Column(Text, nullable=False)
    dinner = Column(Text, nullable=False)

    hostel = orm_relationship("Hostel", back_populates="mess_menus")


class MessFeedback(Base):
    __tablename__ = "mess_feedback"

    feedback_id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("student.student_id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, server_default=func.current_date())
    food_quality = Column(Integer, nullable=False) # 1 to 5
    taste = Column(Integer, nullable=False) # 1 to 5
    cleanliness = Column(Integer, nullable=False) # 1 to 5
    comments = Column(Text)

    student = orm_relationship("Student", back_populates="feedback")
