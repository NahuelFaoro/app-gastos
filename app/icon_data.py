from __future__ import annotations

ICON_CATALOG = [
    ("wallet", "Billetera"), ("bike", "Moto"), ("fuel", "Combustible"),
    ("receipt", "Factura"), ("wrench", "Service"), ("shield", "Seguro"),
    ("road", "Peaje / ruta"), ("car", "Auto / viaje"), ("oil", "Aceite"),
    ("home", "Casa"), ("water", "Agua"), ("wifi", "Internet"),
    ("broom", "Limpieza"), ("flame", "Gas"), ("bolt", "Electricidad"),
    ("cart", "Compras"), ("food", "Comida"), ("play", "Streaming"),
    ("music", "Música"), ("cloud", "Nube"), ("phone", "Teléfono / app"),
    ("graduation", "Educación"), ("book", "Libros"), ("game", "Juegos"),
    ("film", "Cine / series"), ("drink", "Salidas"), ("user", "Personal"),
    ("shirt", "Ropa"), ("scissors", "Peluquería"), ("bag", "Compras personales"),
    ("gift", "Regalos"), ("health", "Salud"), ("pill", "Farmacia"),
    ("medical", "Consulta médica"), ("lab", "Estudios"), ("briefcase", "Trabajo / sueldo"),
    ("users", "Clientes"), ("laptop", "Trabajo digital"), ("tools", "Servicios"),
    ("bank", "Banco"), ("card", "Tarjeta"), ("chart", "Ingresos / inversión"),
    ("package", "Ventas"), ("star", "Otros"), ("pin", "Ubicación"),
    ("store", "Comercio"), ("basket", "Supermercado"), ("soap", "Higiene / limpieza"),
    ("tax", "Impuestos"), ("money", "Pagos"), ("route", "Ruta / viaje"),
    ("parking", "Estacionamiento"), ("coffee", "Café / merienda"), ("plane", "Viajes"),
    ("paw", "Mascotas"), ("dumbbell", "Deporte"), ("house-medical", "Obra social"),
    ("brain", "Psicología"), ("tools-box", "Ferretería"), ("building", "Servicios / empresa"),
    ("transfer", "Transferencia"), ("plus", "Agregar"), ("other", "Otro"),
]

ICON_CATALOG += [('piggy-bank', 'Alcancía / ahorro'), ('coins', 'Monedas'), ('safe', 'Caja fuerte'), ('ticket', 'Entrada / espectáculo'), ('handshake', 'Acuerdo / clientes'), ('tree', 'Naturaleza'), ('dog', 'Perro'), ('cat', 'Gato'), ('baby', 'Bebé'), ('bed', 'Descanso'), ('camera', 'Fotografía'), ('pizza', 'Pizza'), ('cake', 'Torta / cumpleaños'), ('bus', 'Colectivo'), ('train', 'Tren'), ('headphones', 'Auriculares'), ('paint', 'Arte'), ('plant', 'Plantas'), ('investment', 'Inversión')]

ICON_KEYS = [key for key, _ in ICON_CATALOG]
ICON_LABELS = dict(ICON_CATALOG)

LEGACY_ICON_MAP = {
    "💸": "wallet", "💰": "wallet", "🏍️": "bike", "⛽": "fuel", "🔧": "wrench",
    "🛡️": "shield", "🛣️": "road", "🚕": "car", "🛢️": "oil", "🏠": "home",
    "🧾": "receipt", "💧": "water", "📶": "wifi", "🧹": "broom", "🔥": "flame",
    "⚡": "bolt", "🛒": "cart", "🍽️": "food", "▶️": "play", "🎵": "music",
    "☁️": "cloud", "📱": "phone", "🎓": "graduation", "📚": "book", "🧠": "book",
    "🎮": "game", "🎬": "film", "🍻": "drink", "👤": "user", "👕": "shirt",
    "✂️": "scissors", "🛍️": "bag", "🎁": "gift", "🏥": "health", "💊": "pill",
    "🩺": "medical", "🧪": "lab", "💼": "briefcase", "👥": "users", "🧑‍💻": "laptop",
    "🧰": "tools", "🏦": "bank", "💳": "card", "📈": "chart", "📦": "package",
    "✨": "star", "➕": "plus", "📌": "pin", "↔": "transfer",
}


def normalize_icon(value: str | None, name: str | None = None) -> str:
    value = (value or "").strip()
    if value in ICON_KEYS:
        return value
    if value in LEGACY_ICON_MAP:
        return LEGACY_ICON_MAP[value]
    if name:
        lowered = name.lower()
        hints = [
            (("combust", "nafta", "gasolina"), "fuel"), (("moto",), "bike"),
            (("seguro",), "shield"), (("service", "mecanic"), "wrench"), (("peaje",), "road"),
            (("uber", "didi", "taxi"), "car"), (("aceite",), "oil"), (("alquiler", "casa"), "home"),
            (("agua",), "water"), (("wifi", "internet"), "wifi"), (("limpieza", "higiene"), "broom"),
            (("electric", "luz"), "bolt"), (("gas",), "flame"), (("comida",), "food"),
            (("compra", "super"), "cart"), (("youtube", "stream"), "play"), (("spotify", "música", "musica"), "music"),
            (("libro",), "book"), (("curso", "educa"), "graduation"), (("juego",), "game"),
            (("cine", "serie"), "film"), (("ropa",), "shirt"), (("peluquer",), "scissors"),
            (("regalo",), "gift"), (("farmacia",), "pill"), (("salud", "médic", "medic"), "health"),
            (("afip", "impuesto", "monotributo"), "tax"), (("supermerc", "coto", "makro"), "basket"),
            (("ferreter", "herramient"), "tools-box"), (("psic",), "brain"), (("obra social",), "house-medical"),
            (("cliente",), "users"), (("sueldo", "trabajo"), "briefcase"), (("venta",), "package"),
        ]
        for words, key in hints:
            if any(w in lowered for w in words):
                return key
    return "other"


