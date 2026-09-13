from __future__ import annotations

APP_NAME = "App Gastos"
APP_VERSION = "0.39.23"

MONTHS = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
MONTHS_SHORT = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

ACCENT = "#4CCFA9"
POSITIVE = "#45CFA0"
NEGATIVE = "#FF7586"
WARNING = "#F0B45D"

CATEGORY_COLORS = [
    "#4CCFA9", "#45B6D9", "#5F8FF0", "#7A78E8", "#9B73DF",
    "#C86BB5", "#E26F8D", "#EF7E6B", "#E79A55", "#D8B14E",
    "#82BE67", "#54B79A", "#4AA7C8", "#7688B3", "#8A7F99",
]

EXPENSE_CATEGORIES = {
    "Moto": ["Combustible", "Pagos del vehículo", "Service", "Seguro", "Peaje", "Didi/Uber", "Aceite", "Otros"],
    "Casa": ["Alquiler", "Agua", "Wifi", "Limpieza/Higiene", "Gas", "Electricidad", "Compras", "Comida"],
    "Suscripciones": ["YouTube", "Tinder", "Apple", "Google", "Spotify"],
    "Educación": ["Cursos", "Libros", "Otros"],
    "Ocio": ["Salidas", "Juegos", "Cine/Series", "Otros"],
    "Gastos personales": ["Ropa", "Peluquería", "Compras personales", "Otros"],
    "Regalos": ["Regalos"],
    "Salud / Médicos": ["Farmacia", "Consultas", "Estudios", "Otros"],
    "Otros gastos": ["Otros"],
}

INCOME_CATEGORIES = {
    "Sueldo": ["Principal"],
    "Clientes": ["Cliente"],
    "Otros ingresos": ["Ventas", "Servicios", "Otros"],
}

CATEGORY_ICONS = [
    "wallet", "bike", "fuel", "receipt", "wrench", "shield", "road", "car", "oil",
    "home", "water", "wifi", "broom", "flame", "bolt", "cart", "food", "play",
    "music", "cloud", "phone", "graduation", "book", "game", "film", "drink", "user",
    "shirt", "scissors", "bag", "gift", "health", "pill", "medical", "lab", "briefcase",
    "users", "laptop", "tools", "bank", "card", "chart", "package", "star", "pin",
    "store", "basket", "soap", "tax", "money", "route", "parking", "coffee", "plane",
    "paw", "dumbbell", "house-medical", "brain", "tools-box", "building",
    "transfer", "plus", "other",
]
CATEGORY_ICON_BY_NAME = {
    # Gastos principales
    "Moto": "bike", "Casa": "home", "Suscripciones": "play", "Educación": "graduation",
    "Ocio": "game", "Gastos personales": "user", "Regalos": "gift", "Salud / Médicos": "health",
    "Otros gastos": "wallet",
    # Moto
    "Combustible": "fuel", "Pagos del vehículo": "receipt", "Service": "wrench",
    "Seguro": "shield", "Peaje": "road", "Didi/Uber": "car", "Aceite": "oil",
    # Casa
    "Alquiler": "home", "Agua": "water", "Wifi": "wifi", "Limpieza/Higiene": "broom", "Gas": "flame",
    "Electricidad": "bolt", "Compras": "cart", "Comida": "food",
    # Suscripciones / ocio / personales
    "YouTube": "play", "Tinder": "phone", "Apple": "phone", "Google": "cloud", "Spotify": "music",
    "Cursos": "graduation", "Libros": "book", "Salidas": "drink", "Juegos": "game", "Cine/Series": "film",
    "Ropa": "shirt", "Peluquería": "scissors", "Compras personales": "bag",
    "Farmacia": "pill", "Consultas": "medical", "Estudios": "lab",
    # Ingresos
    "Sueldo": "briefcase", "Clientes": "users", "Otros ingresos": "wallet", "Ventas": "package", "Servicios": "tools",
    "Principal": "briefcase", "Cliente": "user",
    "Otros": "star",
}
