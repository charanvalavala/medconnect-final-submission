from datetime import date, time
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Text = Annotated[str, Field(min_length=1, max_length=100)]
PositiveId = Annotated[int, Field(gt=0)]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class FormModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')


class Login(FormModel):
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class Patient(FormModel):
    first_name: str = Field(min_length=1, max_length=50)
    last_name: str = Field(min_length=1, max_length=50)
    date_of_birth: date
    gender: Literal['Male', 'Female', 'Other']
    blood_group: Literal['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'] | None = None
    phone: str = Field(min_length=7, max_length=20)
    email: str | None = Field(default=None, max_length=100)
    address: str = Field(min_length=1, max_length=1000)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)

    @field_validator('date_of_birth')
    @classmethod
    def valid_dob(cls, value):
        if not date(1900, 1, 1) <= value <= date.today():
            raise ValueError('Date of birth must be between 1900 and today.')
        return value


class Booking(FormModel):
    patient_id: PositiveId
    doctor_id: PositiveId
    appointment_date: date
    appointment_time: time
    reason_for_visit: str = Field(min_length=1, max_length=255)


class Reschedule(FormModel):
    appointment_date: date
    appointment_time: time


class AppointmentStatus(FormModel):
    status: Literal['Cancelled', 'No_Show', 'In_Consultation']


class PrescriptionItem(FormModel):
    medicine_id: PositiveId
    dosage: str = Field(min_length=1, max_length=50)
    duration_days: int = Field(gt=0, le=365)
    quantity: int = Field(gt=0, le=10000)


class Encounter(FormModel):
    symptoms: str = Field(min_length=1, max_length=5000)
    diagnosis: str = Field(min_length=1, max_length=5000)
    clinical_notes: str = Field(default='', max_length=10000)
    instructions: str = Field(default='', max_length=5000)
    items: list[PrescriptionItem] = Field(default_factory=list, max_length=30)

    @model_validator(mode='after')
    def unique_medicines(self):
        if len({item.medicine_id for item in self.items}) != len(self.items):
            raise ValueError('Use one prescription line per medicine.')
        return self


class Payment(FormModel):
    payment_method: Literal['Cash', 'Card', 'UPI', 'Insurance', 'NetBanking']


class Medicine(FormModel):
    name: Text
    category: Literal['Antibiotic', 'Analgesic', 'Antihistamine', 'Antipyretic', 'Cardiovascular', 'Antidiabetic', 'Supplements', 'Other']
    manufacturer: Text
    unit_price: Money
    stock_quantity: int = Field(ge=0, le=1000000)
    reorder_level: int = Field(default=20, ge=0, le=1000000)
    expiry_date: date


class StockReceipt(FormModel):
    quantity: int = Field(gt=0, le=1000000)


class MedicinePrice(FormModel):
    unit_price: Money


class Schedule(FormModel):
    doctor_id: PositiveId
    day_of_week: Literal['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    start_time: time
    end_time: time
    slot_duration_minutes: Literal[15, 20, 30, 45, 60] = 30
