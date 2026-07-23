"""Relational schema from the plan: suppliers, projects, deliveries, weather_log.

IMPORTANT (ties to Problem 2 / leakage): `Supplier.avg_delay_days` and
`on_time_rate` are DISPLAY rollups for the dashboard only. They are deliberately
NOT used as model features -- the ML layer recomputes supplier rates *causally*
from the deliveries table (see ml/features.py). Feeding these stored aggregates
into the model would leak the future into the past.
"""
from __future__ import annotations

from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String
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
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    location = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)

    deliveries = relationship("Delivery", back_populates="project")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), index=True)
    material_type = Column(String, nullable=False)
    route_type = Column(String, nullable=False)
    quantity = Column(Integer)
    order_date = Column(Date, nullable=False)
    promised_date = Column(Date, nullable=False)
    actual_date = Column(Date)                       # NULL = not yet delivered
    status = Column(String)                          # on_time | late | pending

    supplier = relationship("Supplier", back_populates="deliveries")
    project = relationship("Project", back_populates="deliveries")


class WeatherLog(Base):
    __tablename__ = "weather_log"

    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    location = Column(String, index=True)
    condition = Column(String)
    severity = Column(Float)
