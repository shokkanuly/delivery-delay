"""Relational schema from the plan: suppliers, projects, deliveries, weather_log.

IMPORTANT (ties to Problem 2 / leakage): `Supplier.avg_delay_days` and
`on_time_rate` are DISPLAY rollups for the dashboard only. They are deliberately
NOT used as model features -- the ML layer recomputes supplier rates *causally*
from the deliveries table (see ml/features.py). Feeding these stored aggregates
into the model would leak the future into the past.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from db.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String, primary_key=True)            # e.g. "S07"
    name = Column(String, nullable=False)
    material_types = Column(JSON, default=list)      # portable list on SQLite & PG
    avg_delay_days = Column(Float)                   # display-only rollup
    on_time_rate = Column(Float)                     # display-only rollup

    deliveries = relationship("Delivery", back_populates="supplier")


class Project(Base):
    """Master project record. The id is the business key from projects.csv
    (`PRJ_001`), so all three engines join on the same identifier."""

    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    priority = Column(String)                # high | medium | low
    start_date = Column(Date)
    end_date = Column(Date)

    deliveries = relationship("Delivery", back_populates="project")
    bookings = relationship("BookingRequest", back_populates="project")
    phases = relationship("BuildPhase", back_populates="project")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), index=True)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    material_type = Column(String, nullable=False)
    route_type = Column(String, nullable=False)
    quantity = Column(Integer)
    distance_km = Column(Float)
    order_date = Column(Date, nullable=False)
    promised_date = Column(Date, nullable=False)
    actual_date = Column(Date)                       # NULL = not yet delivered
    status = Column(String)                          # on_time | late | pending

    supplier = relationship("Supplier", back_populates="deliveries")
    project = relationship("Project", back_populates="deliveries")


class Resource(Base):
    """Engine 2 master data: cranes, trucks and crews available to assign."""

    __tablename__ = "resources"

    id = Column(String, primary_key=True)        # resource_id, e.g. RES_001
    type = Column(String, nullable=False, index=True)
    capacity = Column(Integer)
    home_location = Column(String)

    bookings = relationship("BookingRequest", back_populates="resource")


class BookingRequest(Base):
    """Engine 2 input. `assigned_resource_id` is blank until the solver fills it."""

    __tablename__ = "booking_requests"

    id = Column(String, primary_key=True)        # booking_id, e.g. BK_0001
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    project_priority = Column(String)
    resource_type = Column(String, nullable=False, index=True)
    requested_start = Column(DateTime, nullable=False)
    requested_end = Column(DateTime, nullable=False)
    task = Column(String)
    assigned_resource_id = Column(String, ForeignKey("resources.id"), nullable=True)

    project = relationship("Project", back_populates="bookings")
    resource = relationship("Resource", back_populates="bookings")


class BuildPhase(Base):
    """Engine 3 master data: the build programme each delivery is checked against."""

    __tablename__ = "build_phases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    phase_name = Column(String, nullable=False, index=True)
    phase_order = Column(Integer)
    start_date = Column(Date)
    end_date = Column(Date)

    project = relationship("Project", back_populates="phases")


class PhaseMaterialMap(Base):
    """Which materials belong to which phase.

    An EMPTY `required_materials` means the phase is unconstrained, not that
    every material is forbidden -- see engines/validator/rules.py.
    """

    __tablename__ = "phase_material_map"

    phase_name = Column(String, primary_key=True)
    required_materials = Column(String)          # semicolon-separated, as shipped


class MaterialDelivery(Base):
    """Engine 3 input: deliveries checked against the build programme.

    `flag` is the ground-truth label used to score the rules engine. It is never
    an input to the rules themselves.
    """

    __tablename__ = "material_deliveries"

    id = Column(String, primary_key=True)        # delivery_seq_id
    project_id = Column(String, ForeignKey("projects.id"), index=True)
    material_type = Column(String, nullable=False)
    required_phase = Column(String, nullable=False)
    delivery_date = Column(Date)
    phase_start_date = Column(Date)
    phase_end_date = Column(Date)
    flag = Column(String, nullable=True)


class PredictionLog(Base):
    """Every prediction served, paired with the outcome once it is known.

    This is the evidence table: cross-validated metrics say the model *should*
    work, but realized accuracy on predictions actually served -- scored against
    what really happened -- is the number that convinces a sceptic.

    `model_version` is stamped from the artifact so accuracy can be attributed to
    the exact model that produced each row, and retraining never silently mixes
    old and new predictions together.
    """

    __tablename__ = "prediction_log"

    id = Column(Integer, primary_key=True)
    predicted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    model_version = Column(String, index=True)

    # what was asked about (enough to identify the delivery later)
    delivery_ref = Column(String, index=True)   # caller's own id, if supplied
    supplier_id = Column(String, index=True)
    material_type = Column(String)
    route_type = Column(String)
    quantity = Column(Integer)
    order_date = Column(Date)
    promised_date = Column(Date)

    # what the model said
    predicted_risk = Column(Float, nullable=False)
    predicted_band = Column(String)
    predicted_late = Column(Integer)             # risk >= 0.5, the decision at serve time
    expected_delay_days = Column(Float)

    # what actually happened (filled in later via POST /outcomes)
    actual_date = Column(Date)
    actual_delay_days = Column(Float)
    actual_late = Column(Integer)                # 1/0, NULL until known
    outcome_recorded_at = Column(DateTime)


class WeatherLog(Base):
    __tablename__ = "weather_log"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    location = Column(String, index=True)
    condition = Column(String)
    severity = Column(Float)
