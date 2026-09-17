from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.String(32), primary_key=True)  # e.g. 'osys1200'
    code = db.Column(db.String(32), nullable=False)   # e.g. 'OSYS1200'
    name = db.Column(db.String(128), nullable=False)  # e.g. 'OSYS1200 - Operating Systems'
    subtitle = db.Column(db.String(128), default="")
    badge = db.Column(db.String(64), default="")
    description = db.Column(db.Text, default="")
    preferred_node = db.Column(db.String(64), default="pve2")
    default_username = db.Column(db.String(64), default=".\\Student")
    supports_rdp = db.Column(db.Boolean, default=True)
    supports_spice = db.Column(db.Boolean, default=True)
    custom_notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    templates = db.relationship("LabTemplate", backref="course", lazy=True, cascade="all, delete-orphan")
    student_vms = db.relationship("StudentVM", backref="course", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "subtitle": self.subtitle,
            "badge": self.badge,
            "description": self.description,
            "preferred_node": self.preferred_node,
            "default_username": self.default_username,
            "supports_rdp": self.supports_rdp,
            "supports_spice": self.supports_spice,
            "custom_notes": self.custom_notes or "",
            "templates": [t.to_dict() for t in self.templates if t.is_published],
            "enrolled_students_count": len(self.enrollments) if hasattr(self, "enrollments") else 0
        }

class LabTemplate(db.Model):
    __tablename__ = "lab_templates"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.String(32), db.ForeignKey("courses.id"), nullable=False)
    template_vmid = db.Column(db.Integer, nullable=False)  # e.g. 2002
    name = db.Column(db.String(128), nullable=False)       # e.g. 'Windows 11 Baseline'
    slug = db.Column(db.String(64), nullable=False)        # e.g. 'win11-base'
    description = db.Column(db.Text, default="")
    os_type = db.Column(db.String(32), default="windows")  # 'windows' or 'linux'
    supports_rdp = db.Column(db.Boolean, default=True)
    supports_spice = db.Column(db.Boolean, default=True)
    preferred_node = db.Column(db.String(64), default="pve2")
    default_username = db.Column(db.String(64), default=".\\Student")
    default_password = db.Column(db.String(128), nullable=True)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    student_vms = db.relationship("StudentVM", backref="template", lazy=True)

    def to_dict(self, include_sensitive=False):
        data = {
            "id": self.id,
            "course_id": self.course_id,
            "template_vmid": self.template_vmid,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "os_type": self.os_type,
            "supports_rdp": self.supports_rdp,
            "supports_spice": self.supports_spice,
            "preferred_node": self.preferred_node,
            "default_username": self.default_username,
            "is_published": self.is_published
        }
        if include_sensitive:
            data["default_password"] = self.default_password
        return data

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(64), primary_key=True)  # Student ID / username e.g. 'first.last' or 'W0123456'
    email = db.Column(db.String(128), unique=True, nullable=True)
    name = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(32), default="student")  # 'student', 'instructor', 'admin'
    cohort = db.Column(db.String(64), nullable=True)    # e.g. 'Lab-Y1-ITSM', 'Lab-Y2-ITSM'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    vms = db.relationship("StudentVM", backref="user", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "cohort": self.cohort,
            "enrolled_courses": [e.course_id for e in self.enrollments] if hasattr(self, "enrollments") else []
        }

class Enrollment(db.Model):
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.String(32), db.ForeignKey("courses.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint("user_id", "course_id", name="uq_user_course"),)

    user = db.relationship("User", backref=db.backref("enrollments", lazy=True, cascade="all, delete-orphan"))
    course = db.relationship("Course", backref=db.backref("enrollments", lazy=True, cascade="all, delete-orphan"))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "course_id": self.course_id,
            "course_code": self.course.code if self.course else self.course_id.upper(),
            "course_name": self.course.name if self.course else self.course_id
        }

class StudentVM(db.Model):
    __tablename__ = "student_vms"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(64), db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.String(32), db.ForeignKey("courses.id"), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey("lab_templates.id"), nullable=False)
    vmid = db.Column(db.Integer, unique=True, nullable=False)  # Real Proxmox VMID (e.g. 1042)
    name = db.Column(db.String(128), nullable=False)           # e.g. 'OSYS1200-W0123456-win11-base'
    node = db.Column(db.String(64), nullable=False)            # e.g. 'pve2'
    status = db.Column(db.String(32), default="stopped")       # 'running', 'stopped'
    last_ip = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "course_id": self.course_id,
            "template_id": self.template_id,
            "template_name": self.template.name if self.template else "Custom Lab",
            "vmid": self.vmid,
            "name": self.name,
            "node": self.node,
            "status": self.status,
            "ip": self.last_ip,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
