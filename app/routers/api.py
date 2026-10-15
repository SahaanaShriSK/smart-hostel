from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_
from typing import List, Dict, Any, Optional
from datetime import date, datetime
from decimal import Decimal
import uuid

from ..database import get_db
from .. import models, schemas
from ..auth.jwt import (
    get_current_user,
    get_password_hash,
    verify_password,
    create_access_token,
    RoleChecker
)

# Initialize routers
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
student_router = APIRouter(prefix="/student", tags=["Student Panel"])
warden_router = APIRouter(prefix="/warden", tags=["Warden Panel"])
accountant_router = APIRouter(prefix="/accountant", tags=["Accountant Panel"])
admin_router = APIRouter(prefix="/admin", tags=["Admin Panel"])
common_router = APIRouter(prefix="/common", tags=["Common Endpoints"])


# ============================================================================
# 1. AUTH ROUTER (/api/auth)
# ============================================================================

@auth_router.post("/login", response_model=schemas.Token)
def login(form_data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    # Resolve profile ID and user name
    profile_id = None
    name = user.username
    if user.role == "STUDENT":
        student = db.query(models.Student).filter(models.Student.user_id == user.user_id).first()
        if student:
            profile_id = student.student_id
            name = student.name
    elif user.role == "WARDEN":
        warden = db.query(models.Warden).filter(models.Warden.user_id == user.user_id).first()
        if warden:
            profile_id = warden.warden_id
            name = warden.name
    
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "user_id": user.user_id,
        "profile_id": profile_id,
        "name": name
    }


# ============================================================================
# 2. COMMON ROUTER (/api/common)
# ============================================================================

@common_router.get("/hostels")
def list_hostels(db: Session = Depends(get_db)):
    hostels = db.query(models.Hostel).all()
    result = []
    for h in hostels:
        warden_name = h.warden.name if h.warden else "None Assigned"
        result.append({
            "hostel_id": h.hostel_id,
            "hostel_name": h.hostel_name,
            "hostel_type": h.hostel_type,
            "capacity": h.capacity,
            "warden_name": warden_name
        })
    return result

@common_router.get("/rooms")
def list_rooms(hostel_id: Optional[int] = None, db: Session = Depends(get_db)):
    query = db.query(models.Room)
    if hostel_id:
        query = query.filter(models.Room.hostel_id == hostel_id)
    rooms = query.all()
    
    result = []
    for r in rooms:
        result.append({
            "room_id": r.room_id,
            "hostel_id": r.hostel_id,
            "hostel_name": r.hostel.hostel_name,
            "room_number": r.room_number,
            "floor": r.floor,
            "room_type": r.room_type,
            "capacity": r.capacity,
            "occupied_count": r.occupied_count,
            "status": r.status
        })
    return result

@common_router.get("/notices", response_model=List[schemas.NoticeResponse])
def get_notices(role: Optional[str] = "ALL", db: Session = Depends(get_db)):
    # Notice visibility matching
    audience_filter = ["ALL"]
    if role in ["STUDENT", "WARDEN", "STAFF"]:
        audience_filter.append(role + "S")
        if role == "ACCOUNTANT":
            audience_filter.append("STAFF")

    notices = db.query(models.Notice).filter(
        and_(
            models.Notice.audience.in_(audience_filter),
            (models.Notice.expiry_date == None) | (models.Notice.expiry_date >= date.today())
        )
    ).order_by(models.Notice.created_at.desc()).all()

    res = []
    for n in notices:
        res.append(schemas.NoticeResponse(
            notice_id=n.notice_id,
            title=n.title,
            description=n.description,
            audience=n.audience,
            expiry_date=n.expiry_date,
            created_at=n.created_at,
            created_by=n.created_by,
            author_name=db.query(models.Warden.name).filter(models.Warden.user_id == n.created_by).scalar() or "Admin"
        ))
    return res


# ============================================================================
# 3. STUDENT PANEL ROUTER (/api/student)
# ============================================================================

def get_student_profile(current_user: models.User, db: Session) -> models.Student:
    student = db.query(models.Student).filter(models.Student.user_id == current_user.user_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student profile not found")
    return student

@student_router.get("/profile", response_model=schemas.StudentResponse)
def get_profile(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    
    # Fetch current room
    allocation = db.query(models.RoomAllocation).filter(
        and_(models.RoomAllocation.student_id == student.student_id, models.RoomAllocation.status == "ACTIVE")
    ).first()
    
    res = schemas.StudentResponse.from_orm(student)
    if allocation:
        res.room_number = allocation.room.room_number
        res.hostel_name = allocation.room.hostel.hostel_name
    return res

@student_router.get("/roommates")
def get_roommates(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    
    allocation = db.query(models.RoomAllocation).filter(
        and_(models.RoomAllocation.student_id == student.student_id, models.RoomAllocation.status == "ACTIVE")
    ).first()
    
    if not allocation:
        return []
        
    roommates = db.query(models.Student).join(models.RoomAllocation).filter(
        and_(
            models.RoomAllocation.room_id == allocation.room_id,
            models.RoomAllocation.status == "ACTIVE",
            models.Student.student_id != student.student_id
        )
    ).all()
    
    return [{"student_id": r.student_id, "name": r.name, "roll_no": r.roll_no, "email": r.email, "phone": r.phone} for r in roommates]

@student_router.get("/fees", response_model=List[schemas.StudentFeeResponse])
def get_student_fees(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    fees = db.query(models.StudentFee).filter(models.StudentFee.student_id == student.student_id).all()
    
    result = []
    for f in fees:
        result.append(schemas.StudentFeeResponse(
            fee_id=f.fee_id,
            student_id=f.student_id,
            student_name=student.name,
            roll_no=student.roll_no,
            room_type=f.fee_structure.room_type,
            amount_due=f.amount_due,
            amount_paid=f.amount_paid,
            due_date=f.due_date,
            status=f.status
        ))
    return result

@student_router.post("/payments", response_model=schemas.PaymentResponse)
def make_payment(payment_in: schemas.PaymentCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    
    # Check fee exists
    fee = db.query(models.StudentFee).filter(models.StudentFee.fee_id == payment_in.fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Fee invoice not found")
        
    # Check transaction ID uniqueness
    existing_txn = db.query(models.Payment).filter(models.Payment.transaction_id == payment_in.transaction_id).first()
    if existing_txn:
        raise HTTPException(status_code=400, detail="Transaction ID already exists")

    # Insert payment record (Trigger will update student_fee table)
    db_payment = models.Payment(
        student_id=student.student_id,
        fee_id=payment_in.fee_id,
        amount=payment_in.amount,
        payment_method=payment_in.payment_method,
        transaction_id=payment_in.transaction_id,
        status="SUCCESS"
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    return schemas.PaymentResponse(
        payment_id=db_payment.payment_id,
        student_id=db_payment.student_id,
        student_name=student.name,
        fee_id=db_payment.fee_id,
        amount=db_payment.amount,
        payment_date=db_payment.payment_date,
        payment_method=db_payment.payment_method,
        transaction_id=db_payment.transaction_id,
        status=db_payment.status
    )

@student_router.post("/complaints", response_model=schemas.ComplaintResponse)
def file_complaint(complaint_in: schemas.ComplaintCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    
    # Assign to warden of the student's hostel if allocated, otherwise assign to first warden
    allocation = db.query(models.RoomAllocation).filter(
        and_(models.RoomAllocation.student_id == student.student_id, models.RoomAllocation.status == "ACTIVE")
    ).first()
    
    assigned_to = None
    if allocation and allocation.room.hostel.warden_id:
        assigned_to = allocation.room.hostel.warden_id
    else:
        first_warden = db.query(models.Warden).first()
        if first_warden:
            assigned_to = first_warden.warden_id

    db_complaint = models.Complaint(
        student_id=student.student_id,
        category=complaint_in.category.upper(),
        description=complaint_in.description,
        priority=complaint_in.priority.upper(),
        status="NEW",
        assigned_to=assigned_to
    )
    db.add(db_complaint)
    db.commit()
    db.refresh(db_complaint)

    # Convert to response
    warden_name = db_complaint.warden.name if db_complaint.warden else None
    room_no = allocation.room.room_number if allocation else None

    return schemas.ComplaintResponse(
        complaint_id=db_complaint.complaint_id,
        student_id=db_complaint.student_id,
        student_name=student.name,
        roll_no=student.roll_no,
        room_number=room_no,
        category=db_complaint.category,
        description=db_complaint.description,
        priority=db_complaint.priority,
        created_at=db_complaint.created_at,
        assigned_to=db_complaint.assigned_to,
        assigned_warden_name=warden_name,
        status=db_complaint.status,
        resolved_at=db_complaint.resolved_at,
        resolution=db_complaint.resolution
    )

@student_router.get("/complaints", response_model=List[schemas.ComplaintResponse])
def get_my_complaints(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    
    # Active allocation for room number
    allocation = db.query(models.RoomAllocation).filter(
        and_(models.RoomAllocation.student_id == student.student_id, models.RoomAllocation.status == "ACTIVE")
    ).first()
    room_no = allocation.room.room_number if allocation else None

    complaints = db.query(models.Complaint).filter(models.Complaint.student_id == student.student_id).all()
    
    result = []
    for c in complaints:
        warden_name = c.warden.name if c.warden else None
        result.append(schemas.ComplaintResponse(
            complaint_id=c.complaint_id,
            student_id=c.student_id,
            student_name=student.name,
            roll_no=student.roll_no,
            room_number=room_no,
            category=c.category,
            description=c.description,
            priority=c.priority,
            created_at=c.created_at,
            assigned_to=c.assigned_to,
            assigned_warden_name=warden_name,
            status=c.status,
            resolved_at=c.resolved_at,
            resolution=c.resolution
        ))
    return result

@student_router.post("/leaves", response_model=schemas.LeaveRequestResponse)
def request_leave(leave_in: schemas.LeaveRequestCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    
    # Assign to warden of student's hostel
    allocation = db.query(models.RoomAllocation).filter(
        and_(models.RoomAllocation.student_id == student.student_id, models.RoomAllocation.status == "ACTIVE")
    ).first()
    warden_id = allocation.room.hostel.warden_id if allocation else None
    if not warden_id:
        # Fallback to any warden
        first_warden = db.query(models.Warden).first()
        warden_id = first_warden.warden_id if first_warden else None

    db_leave = models.LeaveRequest(
        student_id=student.student_id,
        pass_type=leave_in.pass_type,
        from_date=leave_in.from_date,
        to_date=leave_in.to_date,
        reason=leave_in.reason,
        destination=leave_in.destination,
        emergency_contact=leave_in.emergency_contact,
        status="PENDING",
        action_by=warden_id
    )
    db.add(db_leave)
    db.commit()
    db.refresh(db_leave)

    return schemas.LeaveRequestResponse(
        leave_id=db_leave.leave_id,
        student_id=db_leave.student_id,
        student_name=student.name,
        roll_no=student.roll_no,
        pass_type=db_leave.pass_type,
        from_date=db_leave.from_date,
        to_date=db_leave.to_date,
        reason=db_leave.reason,
        destination=db_leave.destination,
        emergency_contact=db_leave.emergency_contact,
        status=db_leave.status,
        action_by=db_leave.action_by,
        action_date=db_leave.action_date
    )

@student_router.get("/leaves", response_model=List[schemas.LeaveRequestResponse])
def get_my_leaves(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    leaves = db.query(models.LeaveRequest).filter(models.LeaveRequest.student_id == student.student_id).all()
    
    result = []
    for l in leaves:
        result.append(schemas.LeaveRequestResponse(
            leave_id=l.leave_id,
            student_id=l.student_id,
            student_name=student.name,
            roll_no=student.roll_no,
            pass_type=l.pass_type,
            from_date=l.from_date,
            to_date=l.to_date,
            reason=l.reason,
            destination=l.destination,
            emergency_contact=l.emergency_contact,
            status=l.status,
            action_by=l.action_by,
            action_date=l.action_date
        ))
    return result

@student_router.post("/room-change", response_model=schemas.RoomChangeRequestResponse)
def request_room_change(request_in: schemas.RoomChangeRequestCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    
    # Verify current room
    allocation = db.query(models.RoomAllocation).filter(
        and_(models.RoomAllocation.student_id == student.student_id, models.RoomAllocation.status == "ACTIVE")
    ).first()
    
    if not allocation:
        raise HTTPException(status_code=400, detail="Student has no active room allocation")
        
    # Verify requested room exists and has space
    req_room = db.query(models.Room).filter(models.Room.room_id == request_in.requested_room_id).first()
    if not req_room or req_room.status != "AVAILABLE" or req_room.occupied_count >= req_room.capacity:
        raise HTTPException(status_code=400, detail="Requested room is unavailable or full")

    # Set acting warden
    warden_id = allocation.room.hostel.warden_id if allocation else None

    db_request = models.RoomChangeRequest(
        student_id=student.student_id,
        current_room_id=allocation.room_id,
        requested_room_id=request_in.requested_room_id,
        reason=request_in.reason,
        status="PENDING",
        action_by=warden_id
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)

    return schemas.RoomChangeRequestResponse(
        request_id=db_request.request_id,
        student_id=db_request.student_id,
        student_name=student.name,
        roll_no=student.roll_no,
        current_room_id=db_request.current_room_id,
        current_room_number=allocation.room.room_number,
        requested_room_id=db_request.requested_room_id,
        requested_room_number=req_room.room_number,
        reason=db_request.reason,
        status=db_request.status,
        action_by=db_request.action_by,
        action_date=db_request.action_date
    )

@student_router.get("/attendance", response_model=List[schemas.AttendanceResponse])
def get_my_attendance(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    records = db.query(models.Attendance).filter(models.Attendance.student_id == student.student_id).all()
    
    result = []
    for r in records:
        result.append(schemas.AttendanceResponse(
            attendance_id=r.attendance_id,
            student_id=r.student_id,
            student_name=student.name,
            roll_no=student.roll_no,
            date=r.date,
            status=r.status,
            marked_by=r.marked_by
        ))
    return result

@student_router.get("/mess-menu")
def get_student_mess_menu(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "WARDEN":
        warden = db.query(models.Warden).filter(models.Warden.user_id == current_user.user_id).first()
        if not warden:
            return []
        hostel_ids = [h.hostel_id for h in db.query(models.Hostel).filter(models.Hostel.warden_id == warden.warden_id).all()]
        return db.query(models.MessMenu).filter(models.MessMenu.hostel_id.in_(hostel_ids)).all()
    elif current_user.role in ["ADMIN", "ACCOUNTANT"]:
        return db.query(models.MessMenu).all()
    else:
        # Student
        student = db.query(models.Student).filter(models.Student.user_id == current_user.user_id).first()
        if not student:
            return []
        allocation = db.query(models.RoomAllocation).filter(
            and_(models.RoomAllocation.student_id == student.student_id, models.RoomAllocation.status == "ACTIVE")
        ).first()
        
        if not allocation:
            return db.query(models.MessMenu).all()
            
        return db.query(models.MessMenu).filter(models.MessMenu.hostel_id == allocation.room.hostel_id).all()

@student_router.post("/mess-feedback", response_model=schemas.MessFeedbackResponse)
def submit_mess_feedback(feedback_in: schemas.MessFeedbackCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    student = get_student_profile(current_user, db)
    
    db_feedback = models.MessFeedback(
        student_id=student.student_id,
        food_quality=feedback_in.food_quality,
        taste=feedback_in.taste,
        cleanliness=feedback_in.cleanliness,
        comments=feedback_in.comments,
        date=date.today()
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)

    return schemas.MessFeedbackResponse(
        feedback_id=db_feedback.feedback_id,
        student_id=db_feedback.student_id,
        student_name=student.name,
        date=db_feedback.date,
        food_quality=db_feedback.food_quality,
        taste=db_feedback.taste,
        cleanliness=db_feedback.cleanliness,
        comments=db_feedback.comments
    )


# ============================================================================
# 4. WARDEN PANEL ROUTER (/api/warden)
# ============================================================================

def get_warden_profile(current_user: models.User, db: Session) -> models.Warden:
    warden = db.query(models.Warden).filter(models.Warden.user_id == current_user.user_id).first()
    if not warden:
        raise HTTPException(status_code=404, detail="Warden profile not found")
    return warden

@warden_router.post("/allocate-room")
def allocate_room_api(alloc_in: schemas.RoomAllocationCreate, current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    # Call standard PostgreSQL stored procedure allocate_room(student_id, room_id)
    try:
        stmt = text("SELECT allocate_room(:s_id, :r_id)")
        result = db.execute(stmt, {"s_id": alloc_in.student_id, "r_id": alloc_in.room_id}).scalar()
        db.commit()
        if not result:
            raise HTTPException(status_code=400, detail="Stored procedure allocate_room returned failure status.")
        return {"message": "Room allocated successfully via database function!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database allocation error: {str(e)}")

@warden_router.post("/vacate-room")
def vacate_room_api(student_id: int, current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    # Call standard PostgreSQL stored procedure vacate_room(student_id)
    try:
        stmt = text("SELECT vacate_room(:s_id)")
        result = db.execute(stmt, {"s_id": student_id}).scalar()
        db.commit()
        if not result:
            raise HTTPException(status_code=400, detail="Stored procedure vacate_room returned failure status.")
        return {"message": "Student vacated successfully via database function!"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database vacating error: {str(e)}")

@warden_router.get("/complaints", response_model=List[schemas.ComplaintResponse])
def get_warden_complaints(current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    warden = get_warden_profile(current_user, db)
    
    # Get all complaints assigned to this warden, or unassigned complaints
    complaints = db.query(models.Complaint).filter(
        (models.Complaint.assigned_to == warden.warden_id) | (models.Complaint.assigned_to == None)
    ).all()
    
    result = []
    for c in complaints:
        # Fetch room for the student
        alloc = db.query(models.RoomAllocation).filter(
            and_(models.RoomAllocation.student_id == c.student_id, models.RoomAllocation.status == "ACTIVE")
        ).first()
        room_no = alloc.room.room_number if alloc else None
        
        result.append(schemas.ComplaintResponse(
            complaint_id=c.complaint_id,
            student_id=c.student_id,
            student_name=c.student.name,
            roll_no=c.student.roll_no,
            room_number=room_no,
            category=c.category,
            description=c.description,
            priority=c.priority,
            created_at=c.created_at,
            assigned_to=c.assigned_to,
            assigned_warden_name=c.warden.name if c.warden else None,
            status=c.status,
            resolved_at=c.resolved_at,
            resolution=c.resolution
        ))
    return result

@warden_router.put("/complaints/{complaint_id}", response_model=schemas.ComplaintResponse)
def update_complaint(complaint_id: int, complaint_up: schemas.ComplaintUpdate, current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    warden = get_warden_profile(current_user, db)
    complaint = db.query(models.Complaint).filter(models.Complaint.complaint_id == complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
        
    complaint.status = complaint_up.status.upper()
    if complaint_up.assigned_to:
        complaint.assigned_to = complaint_up.assigned_to
    else:
        complaint.assigned_to = warden.warden_id
        
    if complaint_up.resolution:
        complaint.resolution = complaint_up.resolution

    # Database trigger automatically handles resolved_at when status sets to RESOLVED
    db.commit()
    db.refresh(complaint)

    alloc = db.query(models.RoomAllocation).filter(
        and_(models.RoomAllocation.student_id == complaint.student_id, models.RoomAllocation.status == "ACTIVE")
    ).first()
    room_no = alloc.room.room_number if alloc else None

    return schemas.ComplaintResponse(
        complaint_id=complaint.complaint_id,
        student_id=complaint.student_id,
        student_name=complaint.student.name,
        roll_no=complaint.student.roll_no,
        room_number=room_no,
        category=complaint.category,
        description=complaint.description,
        priority=complaint.priority,
        created_at=complaint.created_at,
        assigned_to=complaint.assigned_to,
        assigned_warden_name=complaint.warden.name if complaint.warden else None,
        status=complaint.status,
        resolved_at=complaint.resolved_at,
        resolution=complaint.resolution
    )

@warden_router.get("/leaves", response_model=List[schemas.LeaveRequestResponse])
def get_warden_leaves(current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    warden = get_warden_profile(current_user, db)
    
    leaves = db.query(models.LeaveRequest).filter(
        (models.LeaveRequest.action_by == warden.warden_id) | (models.LeaveRequest.status == "PENDING")
    ).all()
    
    result = []
    for l in leaves:
        result.append(schemas.LeaveRequestResponse(
            leave_id=l.leave_id,
            student_id=l.student_id,
            student_name=l.student.name,
            roll_no=l.student.roll_no,
            pass_type=l.pass_type,
            from_date=l.from_date,
            to_date=l.to_date,
            reason=l.reason,
            destination=l.destination,
            emergency_contact=l.emergency_contact,
            status=l.status,
            action_by=l.action_by,
            action_date=l.action_date
        ))
    return result

@warden_router.put("/leaves/{leave_id}", response_model=schemas.LeaveRequestResponse)
def process_leave(leave_id: int, leave_up: schemas.LeaveRequestUpdate, current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    warden = get_warden_profile(current_user, db)
    leave = db.query(models.LeaveRequest).filter(models.LeaveRequest.leave_id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave request not found")

    leave.status = leave_up.status.upper()
    leave.action_by = warden.warden_id
    leave.action_date = datetime.now()
    db.commit()
    db.refresh(leave)

    return schemas.LeaveRequestResponse(
        leave_id=leave.leave_id,
        student_id=leave.student_id,
        student_name=leave.student.name,
        roll_no=leave.student.roll_no,
        pass_type=leave.pass_type,
        from_date=leave.from_date,
        to_date=leave.to_date,
        reason=leave.reason,
        destination=leave.destination,
        emergency_contact=leave.emergency_contact,
        status=leave.status,
        action_by=leave.action_by,
        action_date=leave.action_date
    )

@warden_router.get("/room-changes", response_model=List[schemas.RoomChangeRequestResponse])
def get_room_change_requests(current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    warden = get_warden_profile(current_user, db)
    requests = db.query(models.RoomChangeRequest).all()
    
    result = []
    for r in requests:
        result.append(schemas.RoomChangeRequestResponse(
            request_id=r.request_id,
            student_id=r.student_id,
            student_name=r.student.name,
            roll_no=r.student.roll_no,
            current_room_id=r.current_room_id,
            current_room_number=r.current_room.room_number,
            requested_room_id=r.requested_room_id,
            requested_room_number=r.requested_room.room_number,
            reason=r.reason,
            status=r.status,
            action_by=r.action_by,
            action_date=r.action_date
        ))
    return result

@warden_router.put("/room-changes/{request_id}", response_model=schemas.RoomChangeRequestResponse)
def process_room_change(request_id: int, status_up: schemas.RoomChangeRequestUpdate, current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    warden = get_warden_profile(current_user, db)
    req = db.query(models.RoomChangeRequest).filter(models.RoomChangeRequest.request_id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    status_val = status_up.status.upper()
    req.status = status_val
    req.action_by = warden.warden_id
    req.action_date = datetime.now()

    if status_val == "APPROVED":
        # Database transaction: swap allocation
        try:
            # 1. Vacate old room (which sets old allocation Completed)
            stmt_vacate = text("SELECT vacate_room(:s_id)")
            db.execute(stmt_vacate, {"s_id": req.student_id})
            
            # 2. Allocate new room (which inserts new allocation and increments occupancy)
            stmt_allocate = text("SELECT allocate_room(:s_id, :r_id)")
            db.execute(stmt_allocate, {"s_id": req.student_id, "r_id": req.requested_room_id})
            
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Failed to execute allocation changes: {str(e)}")

    db.commit()
    db.refresh(req)

    return schemas.RoomChangeRequestResponse(
        request_id=req.request_id,
        student_id=req.student_id,
        student_name=req.student.name,
        roll_no=req.student.roll_no,
        current_room_id=req.current_room_id,
        current_room_number=req.current_room.room_number,
        requested_room_id=req.requested_room_id,
        requested_room_number=req.requested_room.room_number,
        reason=req.reason,
        status=req.status,
        action_by=req.action_by,
        action_date=req.action_date
    )

@warden_router.post("/attendance")
def mark_attendance(attendance_in: schemas.AttendanceBulkCreate, current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    warden = get_warden_profile(current_user, db)
    
    for r in attendance_in.records:
        # Check if attendance already marked for student on this date
        exist = db.query(models.Attendance).filter(
            and_(models.Attendance.student_id == r.student_id, models.Attendance.date == attendance_in.date)
        ).first()
        
        if exist:
            exist.status = r.status.upper()
            exist.marked_by = warden.warden_id
        else:
            db_record = models.Attendance(
                student_id=r.student_id,
                date=attendance_in.date,
                status=r.status.upper(),
                marked_by=warden.warden_id
            )
            db.add(db_record)
            
    db.commit()
    return {"message": f"Attendance successfully marked for {len(attendance_in.records)} students!"}

@warden_router.get("/attendance")
def view_attendance(date_val: Optional[date] = None, db: Session = Depends(get_db)):
    target_date = date_val or date.today()
    records = db.query(models.Attendance).filter(models.Attendance.date == target_date).all()
    
    res = []
    for r in records:
        res.append({
            "attendance_id": r.attendance_id,
            "student_id": r.student_id,
            "student_name": r.student.name,
            "roll_no": r.student.roll_no,
            "date": r.date,
            "status": r.status,
            "marked_by": r.marked_by
        })
    return res

@warden_router.post("/visitors", response_model=schemas.VisitorResponse)
def register_visitor(visitor_in: schemas.VisitorCreate, current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    warden = get_warden_profile(current_user, db)
    
    db_visitor = models.Visitor(
        student_id=visitor_in.student_id,
        visitor_name=visitor_in.visitor_name,
        relationship=visitor_in.relationship,
        phone=visitor_in.phone,
        visit_date=date.today(),
        entry_time=datetime.now(),
        approved_by=warden.warden_id,
        status="APPROVED"
    )
    db.add(db_visitor)
    db.commit()
    db.refresh(db_visitor)

    return schemas.VisitorResponse(
        visitor_id=db_visitor.visitor_id,
        student_id=db_visitor.student_id,
        student_name=db_visitor.student.name,
        roll_no=db_visitor.student.roll_no,
        visitor_name=db_visitor.visitor_name,
        relationship=db_visitor.relationship,
        phone=db_visitor.phone,
        visit_date=db_visitor.visit_date,
        entry_time=db_visitor.entry_time,
        exit_time=db_visitor.exit_time,
        approved_by=db_visitor.approved_by,
        status=db_visitor.status
    )

@warden_router.put("/visitors/{visitor_id}", response_model=schemas.VisitorResponse)
def checkout_visitor(visitor_id: int, current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    visitor = db.query(models.Visitor).filter(models.Visitor.visitor_id == visitor_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor log not found")
        
    visitor.status = "CHECKED_OUT"
    visitor.exit_time = datetime.now()
    db.commit()
    db.refresh(visitor)

    return schemas.VisitorResponse(
        visitor_id=visitor.visitor_id,
        student_id=visitor.student_id,
        student_name=visitor.student.name,
        roll_no=visitor.student.roll_no,
        visitor_name=visitor.visitor_name,
        relationship=visitor.relationship,
        phone=visitor.phone,
        visit_date=visitor.visit_date,
        entry_time=visitor.entry_time,
        exit_time=visitor.exit_time,
        approved_by=visitor.approved_by,
        status=visitor.status
    )

@warden_router.get("/visitors", response_model=List[schemas.VisitorResponse])
def get_visitors(db: Session = Depends(get_db)):
    visitors = db.query(models.Visitor).order_by(models.Visitor.entry_time.desc()).all()
    result = []
    for v in visitors:
        result.append(schemas.VisitorResponse(
            visitor_id=v.visitor_id,
            student_id=v.student_id,
            student_name=v.student.name,
            roll_no=v.student.roll_no,
            visitor_name=v.visitor_name,
            relationship=v.relationship,
            phone=v.phone,
            visit_date=v.visit_date,
            entry_time=v.entry_time,
            exit_time=v.exit_time,
            approved_by=v.approved_by,
            status=v.status
        ))
    return result

@warden_router.post("/notices", response_model=schemas.NoticeResponse)
def create_notice(notice_in: schemas.NoticeCreate, current_user: models.User = Depends(RoleChecker(["WARDEN", "ADMIN"])), db: Session = Depends(get_db)):
    db_notice = models.Notice(
        title=notice_in.title,
        description=notice_in.description,
        audience=notice_in.audience.upper(),
        expiry_date=notice_in.expiry_date,
        created_by=current_user.user_id
    )
    db.add(db_notice)
    db.commit()
    db.refresh(db_notice)

    author_name = "Admin"
    if current_user.role == "WARDEN":
        warden = db.query(models.Warden).filter(models.Warden.user_id == current_user.user_id).first()
        if warden:
            author_name = warden.name

    return schemas.NoticeResponse(
        notice_id=db_notice.notice_id,
        title=db_notice.title,
        description=db_notice.description,
        audience=db_notice.audience,
        expiry_date=db_notice.expiry_date,
        created_at=db_notice.created_at,
        created_by=db_notice.created_by,
        author_name=author_name
    )


# ============================================================================
# 5. ACCOUNTANT PANEL ROUTER (/api/accountant)
# ============================================================================

@accountant_router.get("/fees", response_model=List[schemas.StudentFeeResponse])
def get_all_fees(current_user: models.User = Depends(RoleChecker(["ACCOUNTANT", "ADMIN"])), db: Session = Depends(get_db)):
    fees = db.query(models.StudentFee).all()
    result = []
    for f in fees:
        result.append(schemas.StudentFeeResponse(
            fee_id=f.fee_id,
            student_id=f.student_id,
            student_name=f.student.name,
            roll_no=f.student.roll_no,
            room_type=f.fee_structure.room_type,
            amount_due=f.amount_due,
            amount_paid=f.amount_paid,
            due_date=f.due_date,
            status=f.status
        ))
    return result

@accountant_router.post("/fees/invoice")
def create_fee_invoice(student_id: int, fee_structure_id: int, due_date: date, current_user: models.User = Depends(RoleChecker(["ACCOUNTANT", "ADMIN"])), db: Session = Depends(get_db)):
    # Fetch structure
    struct = db.query(models.FeeStructure).filter(models.FeeStructure.fee_structure_id == fee_structure_id).first()
    if not struct:
        raise HTTPException(status_code=404, detail="Fee structure not found")
        
    student = db.query(models.Student).filter(models.Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    amount_due = struct.academic_fee + struct.mess_fee + struct.caution_deposit
    
    db_fee = models.StudentFee(
        student_id=student_id,
        fee_structure_id=fee_structure_id,
        amount_due=amount_due,
        amount_paid=0.00,
        due_date=due_date,
        status="PENDING"
    )
    db.add(db_fee)
    db.commit()
    db.refresh(db_fee)
    
    return {"message": "Invoice created successfully", "fee_id": db_fee.fee_id}

@accountant_router.get("/defaulters", response_model=List[Dict[str, Any]])
def get_defaulters(current_user: models.User = Depends(RoleChecker(["ACCOUNTANT", "ADMIN"])), db: Session = Depends(get_db)):
    # Query database view: pending_fees
    try:
        stmt = text("SELECT * FROM pending_fees")
        results = db.execute(stmt).mappings().all()
        return [dict(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query view pending_fees: {str(e)}")

@accountant_router.get("/payments", response_model=List[schemas.PaymentResponse])
def get_all_payments(current_user: models.User = Depends(RoleChecker(["ACCOUNTANT", "ADMIN"])), db: Session = Depends(get_db)):
    payments = db.query(models.Payment).order_by(models.Payment.payment_date.desc()).all()
    res = []
    for p in payments:
        res.append(schemas.PaymentResponse(
            payment_id=p.payment_id,
            student_id=p.student_id,
            student_name=p.student.name,
            fee_id=p.fee_id,
            amount=p.amount,
            payment_date=p.payment_date,
            payment_method=p.payment_method,
            transaction_id=p.transaction_id,
            status=p.status
        ))
    return res

@accountant_router.post("/payments/record", response_model=schemas.PaymentResponse)
def record_manual_payment(payment_in: schemas.PaymentCreate, current_user: models.User = Depends(RoleChecker(["ACCOUNTANT", "ADMIN"])), db: Session = Depends(get_db)):
    # Get student connected to the fee structure
    fee = db.query(models.StudentFee).filter(models.StudentFee.fee_id == payment_in.fee_id).first()
    if not fee:
        raise HTTPException(status_code=404, detail="Student fee structure invoice not found")
        
    db_payment = models.Payment(
        student_id=fee.student_id,
        fee_id=payment_in.fee_id,
        amount=payment_in.amount,
        payment_method=payment_in.payment_method,
        transaction_id=payment_in.transaction_id,
        status="SUCCESS"
    )
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    return schemas.PaymentResponse(
        payment_id=db_payment.payment_id,
        student_id=db_payment.student_id,
        student_name=fee.student.name,
        fee_id=db_payment.fee_id,
        amount=db_payment.amount,
        payment_date=db_payment.payment_date,
        payment_method=db_payment.payment_method,
        transaction_id=db_payment.transaction_id,
        status=db_payment.status
    )


# ============================================================================
# 6. ADMIN PANEL ROUTER (/api/admin)
# ============================================================================

@admin_router.get("/reports/occupancy", response_model=List[Dict[str, Any]])
def get_occupancy_report(current_user: models.User = Depends(RoleChecker(["ADMIN"])), db: Session = Depends(get_db)):
    # Query database view: hostel_occupancy
    try:
        stmt = text("SELECT * FROM hostel_occupancy")
        results = db.execute(stmt).mappings().all()
        return [dict(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query view: {str(e)}")

@admin_router.get("/reports/complaints", response_model=List[Dict[str, Any]])
def get_complaint_summary_report(current_user: models.User = Depends(RoleChecker(["ADMIN"])), db: Session = Depends(get_db)):
    # Query database view: complaint_summary
    try:
        stmt = text("SELECT * FROM complaint_summary")
        results = db.execute(stmt).mappings().all()
        return [dict(r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to query view: {str(e)}")

@admin_router.get("/reports/financials")
def get_financials_report(current_user: models.User = Depends(RoleChecker(["ADMIN", "ACCOUNTANT"])), db: Session = Depends(get_db)):
    # Calculated aggregated reports
    total_due = db.query(func.sum(models.StudentFee.amount_due)).scalar() or Decimal('0.00')
    total_paid = db.query(func.sum(models.StudentFee.amount_paid)).scalar() or Decimal('0.00')
    pending = total_due - total_paid

    # Defaulters count (distinct student_ids with pending balance)
    defaulters_stmt = text("SELECT COUNT(DISTINCT student_id) FROM pending_fees")
    defaulters_count = db.execute(defaulters_stmt).scalar() or 0

    return {
        "total_fees": total_due,
        "collected_fees": total_paid,
        "pending_fees": pending,
        "defaulters": defaulters_count
    }

@admin_router.get("/students")
def get_all_students_admin(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Filter students based on role permissions
    if current_user.role == "WARDEN":
        warden = db.query(models.Warden).filter(models.Warden.user_id == current_user.user_id).first()
        if not warden:
            return []
        hostel_ids = [h.hostel_id for h in db.query(models.Hostel).filter(models.Hostel.warden_id == warden.warden_id).all()]
        
        allocations = db.query(models.RoomAllocation).join(models.Room).filter(
            and_(
                models.RoomAllocation.status == "ACTIVE",
                models.Room.hostel_id.in_(hostel_ids)
            )
        ).all()
        student_ids = [a.student_id for a in allocations]
        students = db.query(models.Student).filter(models.Student.student_id.in_(student_ids)).all()
    else:
        # Admin and Accountant see all students
        students = db.query(models.Student).all()

    res = []
    for s in students:
        alloc = db.query(models.RoomAllocation).filter(
            and_(models.RoomAllocation.student_id == s.student_id, models.RoomAllocation.status == "ACTIVE")
        ).first()
        res.append({
            "student_id": s.student_id,
            "roll_no": s.roll_no,
            "name": s.name,
            "email": s.email,
            "phone": s.phone,
            "department": s.department,
            "year": s.year,
            "gender": s.gender,
            "admission_date": s.admission_date,
            "status": s.status,
            "room_number": alloc.room.room_number if alloc else "Not Allocated",
            "hostel_name": alloc.room.hostel.hostel_name if alloc else "N/A"
        })
    return res

@admin_router.post("/students")
def create_student_admin(student_in: schemas.StudentCreate, current_user: models.User = Depends(RoleChecker(["ADMIN"])), db: Session = Depends(get_db)):
    # Check if student credentials exist
    exist_user = db.query(models.User).filter(models.User.username == student_in.username).first()
    if exist_user:
        raise HTTPException(status_code=400, detail="Username already exists")
        
    exist_roll = db.query(models.Student).filter(models.Student.roll_no == student_in.roll_no).first()
    if exist_roll:
        raise HTTPException(status_code=400, detail="Roll number already exists")

    # Transaction: Create User + Student Profile
    try:
        db_user = models.User(
            username=student_in.username,
            password_hash=get_password_hash(student_in.password),
            role="STUDENT"
        )
        db.add(db_user)
        db.flush()

        db_student = models.Student(
            user_id=db_user.user_id,
            roll_no=student_in.roll_no,
            name=student_in.name,
            email=student_in.email,
            phone=student_in.phone,
            department=student_in.department,
            year=student_in.year,
            gender=student_in.gender,
            date_of_birth=student_in.date_of_birth,
            status="ACTIVE"
        )
        db.add(db_student)
        db.commit()
        return {"message": "Student created successfully", "student_id": db_student.student_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Creation failed: {str(e)}")

@admin_router.post("/wardens")
def create_warden_admin(username: str, password_hash_val: str, name: str, email: str, phone: Optional[str] = None, current_user: models.User = Depends(RoleChecker(["ADMIN"])), db: Session = Depends(get_db)):
    exist_user = db.query(models.User).filter(models.User.username == username).first()
    if exist_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    try:
        db_user = models.User(
            username=username,
            password_hash=get_password_hash(password_hash_val),
            role="WARDEN"
        )
        db.add(db_user)
        db.flush()

        db_warden = models.Warden(
            user_id=db_user.user_id,
            name=name,
            email=email,
            phone=phone
        )
        db.add(db_warden)
        db.commit()
        return {"message": "Warden created successfully", "warden_id": db_warden.warden_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Creation failed: {str(e)}")

@admin_router.post("/hostels")
def create_hostel_admin(hostel_in: schemas.HostelCreate, current_user: models.User = Depends(RoleChecker(["ADMIN"])), db: Session = Depends(get_db)):
    db_hostel = models.Hostel(
        hostel_name=hostel_in.hostel_name,
        hostel_type=hostel_in.hostel_type.upper(),
        capacity=hostel_in.capacity,
        warden_id=hostel_in.warden_id
    )
    db.add(db_hostel)
    db.commit()
    db.refresh(db_hostel)
    return {"message": "Hostel created successfully", "hostel_id": db_hostel.hostel_id}

@admin_router.post("/rooms")
def create_room_admin(room_in: schemas.RoomCreate, current_user: models.User = Depends(RoleChecker(["ADMIN"])), db: Session = Depends(get_db)):
    db_room = models.Room(
        hostel_id=room_in.hostel_id,
        room_number=room_in.room_number,
        floor=room_in.floor,
        room_type=room_in.room_type.upper(),
        capacity=room_in.capacity,
        occupied_count=0,
        status="AVAILABLE"
    )
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return {"message": "Room created successfully", "room_id": db_room.room_id}

@admin_router.get("/inventory", response_model=List[schemas.InventoryResponse])
def get_inventory_admin(db: Session = Depends(get_db)):
    items = db.query(models.Inventory).all()
    res = []
    for i in items:
        res.append(schemas.InventoryResponse(
            item_id=i.item_id,
            hostel_id=i.hostel_id,
            hostel_name=i.hostel.hostel_name,
            item_name=i.item_name,
            total_qty=i.total_qty,
            occupied_qty=i.occupied_qty,
            damaged_qty=i.damaged_qty,
            available_qty=i.total_qty - i.occupied_qty - i.damaged_qty
        ))
    return res

@admin_router.post("/inventory/transaction")
def create_inventory_transaction(tx_in: schemas.InventoryTransactionCreate, current_user: models.User = Depends(RoleChecker(["ADMIN", "WARDEN"])), db: Session = Depends(get_db)):
    item = db.query(models.Inventory).filter(models.Inventory.item_id == tx_in.item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    try:
        tx_type = tx_in.transaction_type.upper()
        # Adjust inventory numbers based on transaction
        if tx_type == "ADD":
            item.total_qty += tx_in.quantity
        elif tx_type == "REMOVE":
            if item.total_qty < tx_in.quantity:
                raise HTTPException(status_code=400, detail="Not enough items to remove")
            item.total_qty -= tx_in.quantity
        elif tx_type == "DAMAGE_REPORT":
            if (item.total_qty - item.damaged_qty) < tx_in.quantity:
                raise HTTPException(status_code=400, detail="Reported damage exceeds existing working items")
            item.damaged_qty += tx_in.quantity
        elif tx_type == "REPAIR_REPORT":
            if item.damaged_qty < tx_in.quantity:
                raise HTTPException(status_code=400, detail="Reported repair exceeds existing damaged items")
            item.damaged_qty -= tx_in.quantity

        db_tx = models.InventoryTransaction(
            item_id=tx_in.item_id,
            transaction_type=tx_type,
            quantity=tx_in.quantity,
            remarks=tx_in.remarks
        )
        db.add(db_tx)
        db.commit()
        return {"message": "Inventory transaction logged successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
