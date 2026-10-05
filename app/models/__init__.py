# Importer TOUS les modèles ici : Alembic et create_all doivent voir l'ensemble des tables.
from app.models.user import User, RoleEnum, GenderEnum  # noqa: F401
from app.models.student_profile import StudentProfile, PhaseEnum  # noqa: F401
from app.models.vehicle import Vehicle, VehicleStatusEnum  # noqa: F401
from app.models.driving_session import DrivingSession, SessionAttendance, SessionStatusEnum  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.exam_session import ExamSession  # noqa: F401
from app.models.exam_registration import ExamRegistration, RegistrationStatusEnum  # noqa: F401
from app.models.settings import Pricing, AutoEcoleInfo  # noqa: F401
from app.models.notification import Notification  # noqa: F401
