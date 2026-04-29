from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Installation(Base):
    __tablename__ = "installations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )

    measurements: Mapped[list["Measurement"]] = relationship(
        back_populates="installation"
    )


class Measurement(Base):
    __tablename__ = "measurements"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    installation_id: Mapped[str] = mapped_column(
        String, ForeignKey("installations.id"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    pushed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, server_default=func.now()
    )

    # Free chlorine unit (left)
    chlorine_status: Mapped[str] = mapped_column(String, nullable=False)
    chlorine_diagnosis: Mapped[str | None] = mapped_column(String)
    chlorine_pattern: Mapped[str | None] = mapped_column(String)
    chlorine_blinking: Mapped[list[str] | None] = mapped_column(JSON)
    chlorine_solid: Mapped[list[str] | None] = mapped_column(JSON)
    chlorine_summary: Mapped[str | None] = mapped_column(Text)
    chlorine_action: Mapped[bool] = mapped_column(nullable=False, default=False)
    chlorine_recommended: Mapped[str | None] = mapped_column(Text)

    # pH unit (right)
    ph_status: Mapped[str] = mapped_column(String, nullable=False)
    ph_diagnosis: Mapped[str | None] = mapped_column(String)
    ph_pattern: Mapped[str | None] = mapped_column(String)
    ph_blinking: Mapped[list[str] | None] = mapped_column(JSON)
    ph_solid: Mapped[list[str] | None] = mapped_column(JSON)
    ph_summary: Mapped[str | None] = mapped_column(Text)
    ph_action: Mapped[bool] = mapped_column(nullable=False, default=False)
    ph_recommended: Mapped[str | None] = mapped_column(Text)

    raw_response: Mapped[str | None] = mapped_column(Text)

    installation: Mapped[Installation] = relationship(back_populates="measurements")

    __table_args__ = (
        Index("idx_measurements_inst_captured", "installation_id", "captured_at"),
    )
