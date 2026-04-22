from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Installation(Base):
    __tablename__ = "installations"
    id = Column(String, primary_key=True)
    last_seen = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    measurements = relationship("Measurement", back_populates="installation")


class Measurement(Base):
    __tablename__ = "measurements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    installation_id = Column(String, ForeignKey("installations.id"), nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False)
    pushed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Free chlorine unit (left)
    chlorine_status = Column(String, nullable=False)
    chlorine_diagnosis = Column(String)
    chlorine_pattern = Column(String)
    chlorine_blinking = Column(JSON)  # List[str]
    chlorine_solid = Column(JSON)  # List[str]
    chlorine_summary = Column(Text)
    chlorine_action = Column(Boolean, nullable=False, default=False)
    chlorine_recommended = Column(Text)

    # pH unit (right)
    ph_status = Column(String, nullable=False)
    ph_diagnosis = Column(String)
    ph_pattern = Column(String)
    ph_blinking = Column(JSON)  # List[str]
    ph_solid = Column(JSON)  # List[str]
    ph_summary = Column(Text)
    ph_action = Column(Boolean, nullable=False, default=False)
    ph_recommended = Column(Text)

    raw_response = Column(Text)

    installation = relationship("Installation", back_populates="measurements")

    __table_args__ = (
        Index("idx_measurements_inst_captured", "installation_id", "captured_at"),
    )
