"""
 __  __     __     ______     __  __     ______     __    __     ______    
/\ \_\ \   /\ \   /\  ___\   /\ \_\ \   /\  __ \   /\ "-./  \   /\  __ \   
\ \  __ \  \ \ \  \ \___  \  \ \  __ \  \ \  __ \  \ \ \-./\ \  \ \ \/\ \  
 \ \_\ \_\  \ \_\  \/\_____\  \ \_\ \_\  \ \_\ \_\  \ \_\ \ \_\  \ \_____\ 
  \/_/\/_/   \/_/   \/_____/   \/_/\/_/   \/_/\/_/   \/_/  \/_/   \/_____/ 
                                                                           
"""

from pathlib import Path

import pandas as pd
from flask import Flask, render_template, request, url_for
from sqlalchemy import MetaData, Table, asc, create_engine, desc, func, or_, select

import dataloader

BASE_DIR = Path(__file__).resolve().parent
engine = create_engine(f"sqlite:///{BASE_DIR / 'hdb_resale.db'}")

# On first run this downloads the dataset and builds the SQLite database.
dataloader.ensure_data(engine)

metadata = MetaData()
resale = Table(dataloader.TABLE_NAME, metadata, autoload_with=engine)

app = Flask(__name__)

PAGE_SIZE = 50
SORTABLE_COLUMNS = [c.name for c in resale.columns]

# Columns whose distinct values populate the filter dropdowns.
DROPDOWN_COLUMNS = ("month", "town", "flat_type", "storey_range", "flat_model")

# (query-string argument, database column, operator)
RANGE_FILTERS = [
    ("area_min", "floor_area_sqm", "ge"),
    ("area_max", "floor_area_sqm", "le"),
    ("price_min", "resale_price", "ge"),
    ("price_max", "resale_price", "le"),
    ("lease_min", "lease_commence_date", "ge"),
    ("lease_max", "lease_commence_date", "le"),
    ("remaining_min", "remaining_lease_years", "ge"),
    ("remaining_max", "remaining_lease_years", "le"),
]


def get_filter_options():
    options = {}
    for col in DROPDOWN_COLUMNS:
        stmt = select(resale.c[col]).distinct().order_by(resale.c[col])
        options[col] = pd.read_sql(stmt, engine)[col].tolist()
    return options


FILTER_OPTIONS = get_filter_options()


def build_conditions(args):
    conds = []

    if args.get("month_from"):
        conds.append(resale.c.month >= args["month_from"])
    if args.get("month_to"):
        conds.append(resale.c.month <= args["month_to"])

    for col in ("town", "flat_type", "storey_range", "flat_model"):
        value = args.get(col, "").strip()
        if value:
            conds.append(resale.c[col] == value)

    search = args.get("search", "").strip()
    if search:
        like = f"%{search}%"
        conds.append(or_(resale.c.block.ilike(like), resale.c.street_name.ilike(like)))

    for arg, col, op in RANGE_FILTERS:
        raw = args.get(arg, "").strip()
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        conds.append(resale.c[col] >= value if op == "ge" else resale.c[col] <= value)

    return conds


@app.route("/")
def index():
    args = request.args
    conds = build_conditions(args)

    stats_stmt = select(
        func.count().label("n"),
        func.avg(resale.c.resale_price).label("avg_price"),
        func.min(resale.c.resale_price).label("min_price"),
        func.max(resale.c.resale_price).label("max_price"),
        func.avg(resale.c.price_per_sqm).label("avg_psm"),
    ).where(*conds)
    stats = pd.read_sql(stats_stmt, engine).iloc[0]

    sort = args.get("sort") if args.get("sort") in SORTABLE_COLUMNS else "month"
    order = "asc" if args.get("order") == "asc" else "desc"

    total = int(stats["n"])
    pages = max(-(-total // PAGE_SIZE), 1)
    try:
        page = min(max(int(args.get("page", 1)), 1), pages)
    except ValueError:
        page = 1

    rows_stmt = (
        select(resale)
        .where(*conds)
        .order_by(asc(resale.c[sort]) if order == "asc" else desc(resale.c[sort]))
        .limit(PAGE_SIZE)
        .offset((page - 1) * PAGE_SIZE)
    )
    rows = pd.read_sql(rows_stmt, engine).to_dict("records")

    return render_template(
        "index.html",
        rows=rows,
        stats=stats,
        options=FILTER_OPTIONS,
        total=total,
        page=page,
        pages=pages,
        sort=sort,
        order=order,
    )


@app.template_global()
def url_with(**overrides):
    """Current URL with some query parameters replaced (for sorting/pagination links)."""
    params = request.args.to_dict()
    params.update(overrides)
    return url_for("index", **{k: v for k, v in params.items() if v not in (None, "")})


@app.template_filter("num")
def format_number(value, decimals=0):
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return value


if __name__ == "__main__":
    app.run(debug=True, port=5000)
