from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    synthetic_identifier: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    age: Mapped[int] = mapped_column(Integer, index=True)
    sex: Mapped[str] = mapped_column(String(16), index=True)

    diseases: Mapped[list["PatientDisease"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    variants: Mapped[list["PatientVariant"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )
    treatments: Mapped[list["Treatment"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class Disease(Base):
    __tablename__ = "diseases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))


class PatientDisease(Base):
    __tablename__ = "patient_diseases"
    __table_args__ = (UniqueConstraint("patient_id", "disease_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    disease_id: Mapped[int] = mapped_column(ForeignKey("diseases.id", ondelete="CASCADE"))
    diagnosed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="diseases")
    disease: Mapped[Disease] = relationship()


class GeneticVariant(Base):
    __tablename__ = "genetic_variants"
    __table_args__ = (
        UniqueConstraint("code"),
        Index("ix_genetic_variant_gene", "gene"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(128), index=True)
    gene: Mapped[str] = mapped_column(String(64), index=True)
    chromosome: Mapped[str] = mapped_column(String(16))
    position: Mapped[int] = mapped_column(Integer)
    reference_allele: Mapped[str] = mapped_column(String(32))
    alternate_allele: Mapped[str] = mapped_column(String(32))


class PatientVariant(Base):
    __tablename__ = "patient_variants"
    __table_args__ = (UniqueConstraint("patient_id", "variant_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    variant_id: Mapped[int] = mapped_column(
        ForeignKey("genetic_variants.id", ondelete="CASCADE")
    )
    genotype: Mapped[str] = mapped_column(String(16))

    patient: Mapped[Patient] = relationship(back_populates="variants")
    variant: Mapped[GeneticVariant] = relationship()


class Therapy(Base):
    __tablename__ = "therapies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))


class Treatment(Base):
    __tablename__ = "treatments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"))
    therapy_id: Mapped[int] = mapped_column(ForeignKey("therapies.id", ondelete="CASCADE"))
    started_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="treatments")
    therapy: Mapped[Therapy] = relationship()
    outcome: Mapped["TreatmentOutcome | None"] = relationship(
        back_populates="treatment", cascade="all, delete-orphan", uselist=False
    )


class TreatmentOutcome(Base):
    __tablename__ = "treatment_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    treatment_id: Mapped[int] = mapped_column(
        ForeignKey("treatments.id", ondelete="CASCADE"), unique=True
    )
    response: Mapped[str] = mapped_column(String(32), index=True)
    evaluated_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    treatment: Mapped[Treatment] = relationship(back_populates="outcome")


class ResponseCategory(Base):
    __tablename__ = "response_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    is_positive: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
