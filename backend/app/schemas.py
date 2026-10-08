"""Lo que entra por la API: cuerpos de los pedidos."""
from pydantic import BaseModel


class Secret(BaseModel):
    value: str


class Toggle(BaseModel):
    value: bool


class Order(BaseModel):
    ids: list[int]


# --- super admin ---

class NewTenant(BaseModel):
    name: str
    slug: str
    admin_password: str
    client_code: str
    whatsapp: str = ""


class NewStore(BaseModel):
    name: str
    slug: str
    plan: str = "free"  # "premium": se crea en Gratis y queda el pedido de Premium


class TenantPatch(BaseModel):
    name: str | None = None
    logo: str | None = None
    accent: str | None = None
    highlight: str | None = None
    notes: str | None = None
    plan: str | None = None
    premium_until: str | None = None  # fecha ISO, o "" = sin vencimiento


# --- admin de la disquería ---

class Message(BaseModel):
    template: str
    line: str


class Contact(BaseModel):
    address: str = ""
    city: str = ""
    phone: str = ""
    email: str = ""
    hours: str = ""
    instagram: str = ""


class ImportPlan(BaseModel):
    header_row: int
    mapping: dict[int, str]  # índice de columna -> campo, "custom", "extra" o "ignore"


class SectionIn(BaseModel):
    name: str | None = None
    visible: bool | None = None


class ItemIn(BaseModel):
    disc_id: int


class GroupIn(BaseModel):
    name: str | None = None
    visible: bool | None = None


class BannerIn(BaseModel):
    title: str | None = None
    text: str | None = None
    button_label: str | None = None
    button_link: str | None = None
    visible: bool | None = None


class Layout(BaseModel):
    tokens: list[str]
