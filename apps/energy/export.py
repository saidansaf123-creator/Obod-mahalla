"""Бирлаштирилган маълумотлар Excel файлини тузиш."""
import datetime

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .merge import CATEGORIES, FILES, RES
from .models import District, Goal, Mahalla, Transformer

FONT = "Arial"
F_BASE = Font(name=FONT, size=10)
F_BOLD = Font(name=FONT, size=10, bold=True)
F_HEAD = Font(name=FONT, size=10, bold=True, color="FFFFFF")
F_TITLE = Font(name=FONT, size=14, bold=True)
F_NOTE = Font(name=FONT, size=9, italic=True, color="555555")
FILL_HEAD = PatternFill("solid", fgColor="1F2937")
FILL_TOTAL = PatternFill("solid", fgColor="E5E7EB")
FILL_STATUS = {"good": PatternFill("solid", fgColor="DCFCE7"), "warn": PatternFill("solid", fgColor="FEF3C7"),
               "crit": PatternFill("solid", fgColor="FEE2E2")}
THIN = Side(style="thin", color="D1D5DB")
TOP = Border(top=Side(style="medium", color="111827"))
STATUS_UZ = {"good": "Яшил", "warn": "Сариқ", "crit": "Қизил"}
PRIO_UZ = {"high": "Юқори", "medium": "Ўрта", "low": "Паст"}

S_DIST, S_MAH, S_TP, S_WORK, S_FIX, S_INFO = ("Туманлар", "Маҳаллалар", "ТП лар", "Дастур ишлари",
                                               "Тузатишлар", "Маълумот")


def q(sheet):
    return f"'{sheet}'"


def _table(ws, headers, widths, start_row=1):
    for j, (h, w) in enumerate(zip(headers, widths), start=1):
        c = ws.cell(row=start_row, column=j, value=h)
        c.font, c.fill = F_HEAD, FILL_HEAD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[start_row].height = 32
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)


def _fmt_row(ws, row, formats):
    for j, f in formats.items():
        ws.cell(row=row, column=j).number_format = f


def _style_body(ws, first, last, ncols):
    for r in ws.iter_rows(min_row=first, max_row=last, max_col=ncols):
        for c in r:
            c.font = F_BASE
            c.border = Border(bottom=THIN)


def _total_row(ws, row, ncols, label_col=1, label="ЖАМИ"):
    ws.cell(row=row, column=label_col, value=label)
    for j in range(1, ncols + 1):
        c = ws.cell(row=row, column=j)
        c.font, c.fill, c.border = F_BOLD, FILL_TOTAL, TOP


def export_workbook(path, merged):
    wb = Workbook()
    districts = list(District.objects.all())
    tps = list(Transformer.objects.select_related("district", "mahalla").order_by(
        "district__name_cyr", "mahalla__name_cyr", "number"))
    goals = {g.mahalla_id: g for g in Goal.objects.all()}
    mahallas = list(Mahalla.objects.select_related("district").order_by("district__name_cyr", "name_cyr"))

    # ---------------------------------------------------------------- ТП лар
    ws = wb.active
    ws.title = S_TP
    head = ["№", "Туман", "Маҳалла", "ТП рақами", "Подстанция", "Фидер", "Эгаси", "Жами истеъмолчи",
            "Аҳоли", "Улгуржи", "Қувват, кВА", "Кунлик истеъмол, кВт·соат", "Ойлик истеъмол, кВт·соат",
            "Йиллик истеъмол, кВт·соат", "Кучланиш А, В", "Кучланиш Б, В", "Кучланиш С, В", "Ток А, А",
            "Ток Б, А", "Ток С, А", "cos φ", "Юкланиш", "Ҳақиқий юклама, кВА", "Ҳисоблагич ҳолати",
            "Саломатлик индекси", "Ҳолат", "Асосий муаммо", "2027 дастурида", "Обод файлида",
            "Эски туман (Обод файли)", "Эски маҳалла (Обод файли)", "Маҳалла манбаси"]
    widths = [6, 15, 20, 13, 30, 22, 10, 11, 9, 9, 10, 13, 14, 15, 10, 10, 10, 9, 9, 9, 8, 10, 12, 22,
              11, 14, 30, 11, 10, 16, 20, 34]
    _table(ws, head, widths)
    r = 1
    for i, t in enumerate(tps, start=1):
        r = i + 1
        rep = t.report
        src = ("2.1-илова: маҳалла ишлари рўйхатида ТП тилга олинган" if t.in_program
               else "Аниқланмади — ТП дастурда тилга олинмаган")
        vals = [i, t.district.name_cyr, t.mahalla.name_cyr if t.mahalla else "Аниқланмаган", t.number,
                t.substation, t.feeder, t.owner, t.consumers_total, t.consumers_household,
                t.consumers_commercial, t.capacity_kva, t.daily_kwh, f"=IF(L{r}=\"\",\"\",L{r}*30)",
                f"=IF(M{r}=\"\",\"\",M{r}*12)", t.voltage_a, t.voltage_b, t.voltage_c, t.current_a, t.current_b,
                t.current_c, t.pf, t.load_factor, f"=IF(V{r}=\"\",\"\",V{r}*K{r})", t.meter_state, rep.score,
                STATUS_UZ[rep.status], rep.issues[0].title if rep.issues else "—",
                "Ҳа" if t.in_program else "Йўқ", "Ҳа" if t.in_obod else "Йўқ", t.obod_district, t.obod_mahalla,
                src]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=r, column=j, value=v)
        ws.cell(row=r, column=26).fill = FILL_STATUS[rep.status]
    last = r
    _style_body(ws, 2, last, len(head))
    for rr in range(2, last + 2):
        _fmt_row(ws, rr, {8: "#,##0", 9: "#,##0", 10: "#,##0", 11: "#,##0", 12: "#,##0.0", 13: "#,##0",
                          14: "#,##0", 15: "0.0", 16: "0.0", 17: "0.0", 18: "0.0", 19: "0.0", 20: "0.0",
                          21: "0.000", 22: "0.0%", 23: "#,##0.0"})
    tot = last + 1
    _total_row(ws, tot, len(head), label_col=2)
    for col in "HIJKLMNW":
        ws[f"{col}{tot}"] = f"=SUM({col}2:{col}{last})"
    ws[f"V{tot}"] = f"=IFERROR(W{tot}/K{tot},0)"
    ws[f"V{tot}"].comment = Comment("Қувват бўйича ўртача юкланиш: жами ҳақиқий юклама / жами қувват", "Обод маҳалла")
    ws.auto_filter.ref = f"A1:{get_column_letter(len(head))}{last}"
    ws["L1"].comment = Comment("Манфий/нол қиймат — ҳисоблагич хатоси (манбадагидек қолдирилган).", "Обод маҳалла")
    ws["O1"].comment = Comment("А/Б/С — тизим ҳисоботидаги L1/L2/L3 сарлавҳалари бўйича.", "Обод маҳалла")

    # ---------------------------------------------------------------- Дастур ишлари
    ws = wb.create_sheet(S_WORK)
    head = ["№", "Туман", "Маҳалла", "Иш номи", "Йўналиш", "Ўлчов бирлиги", "Миқдори", "Нархи, млн сўм",
            "Тегишли ТП лар", "2.1-илова қатори"]
    _table(ws, head, [6, 15, 20, 70, 30, 12, 10, 13, 18, 10])
    r = 1
    for i, w in enumerate(merged.works, start=1):
        r = i + 1
        vals = [i, RES[w.res][0], w.mahalla, w.title, CATEGORIES[w.kind][0], w.unit, w.quantity, w.cost,
                ", ".join(w.tps), w.row]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=r, column=j, value=v)
        ws.cell(row=r, column=4).alignment = Alignment(wrap_text=True, vertical="top")
    wlast = r
    _style_body(ws, 2, wlast, len(head))
    for rr in range(2, wlast + 2):
        _fmt_row(ws, rr, {7: "#,##0.00", 8: "#,##0.00"})
    tot = wlast + 1
    _total_row(ws, tot, len(head), label_col=2)
    ws[f"H{tot}"] = f"=SUM(H2:H{wlast})"
    ws.auto_filter.ref = f"A1:J{wlast}"

    # ---------------------------------------------------------------- Маҳаллалар (формулалар)
    ws = wb.create_sheet(S_MAH, 0)
    head = ["Туман", "Маҳалла", "ТП сони", "Истеъмолчилар", "Қувват, кВА", "Кунлик истеъмол, кВт·соат",
            "Юкланиш", "Ўртача саломатлик", "Ишлар сони", "Бюджет, млн сўм", "Мақсад (2027)", "Устуворлик"]
    _table(ws, head, [15, 22, 9, 13, 12, 15, 10, 12, 10, 14, 60, 11])
    T, W = q(S_TP), q(S_WORK)
    r = 1
    for i, m in enumerate(mahallas, start=1):
        r = i + 1
        g = goals.get(m.id)
        crit = f"{T}!$B$2:$B${last},$A{r},{T}!$C$2:$C${last},$B{r}"
        vals = [m.district.name_cyr, m.name_cyr,
                f"=COUNTIFS({crit})",
                f"=SUMIFS({T}!$H$2:$H${last},{crit})",
                f"=SUMIFS({T}!$K$2:$K${last},{crit})",
                f"=SUMIFS({T}!$L$2:$L${last},{crit},{T}!$L$2:$L${last},\">0\")",
                f"=IFERROR(SUMIFS({T}!$W$2:$W${last},{crit})/E{r},\"\")",
                f"=IFERROR(AVERAGEIFS({T}!$Y$2:$Y${last},{crit}),\"\")",
                f"=COUNTIFS({W}!$B$2:$B${wlast},$A{r},{W}!$C$2:$C${wlast},$B{r})",
                f"=SUMIFS({W}!$H$2:$H${wlast},{W}!$B$2:$B${wlast},$A{r},{W}!$C$2:$C${wlast},$B{r})",
                g.title if g else "", PRIO_UZ.get(g.priority, "") if g else ""]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=r, column=j, value=v)
    mlast = r
    _style_body(ws, 2, mlast, len(head))
    for rr in range(2, mlast + 2):
        _fmt_row(ws, rr, {3: "#,##0", 4: "#,##0", 5: "#,##0", 6: "#,##0", 7: "0.0%", 8: "0", 9: "#,##0",
                          10: "#,##0.00"})
    tot = mlast + 1
    _total_row(ws, tot, len(head))
    for col in "CDEFIJ":
        ws[f"{col}{tot}"] = f"=SUM({col}2:{col}{mlast})"
    ws.auto_filter.ref = f"A1:L{mlast}"

    # ---------------------------------------------------------------- Туманлар
    ws = wb.create_sheet(S_DIST, 0)
    head = ["Туман", "РЭС (тизимда)", "ТП сони (тизим)", "Истеъмолчилар", "Аҳоли", "Улгуржи", "Қувват, кВА",
            "Кунлик истеъмол, кВт·соат", "Ўртача юкланиш", "Муаммоли ТП", "Маҳаллалар (дастур)",
            "Дастурдаги ТП", "Дастур ишлари", "Бюджет — ишлар йиғиндиси, млн сўм", "Бюджет — 2-илова, млн сўм",
            "Фарқ, млн сўм"]
    _table(ws, head, [15, 20, 11, 13, 12, 11, 12, 15, 11, 11, 12, 11, 11, 17, 17, 13])
    M = q(S_MAH)
    r = 1
    for i, d in enumerate(districts, start=1):
        r = i + 1
        s = d.system_stats
        vals = [d.name_cyr, d.res_name, s.get("tp_count"), s.get("consumers"), s.get("household"),
                s.get("commercial"), s.get("capacity_kva"), s.get("daily_kwh"), (s.get("load_pct") or 0) / 100,
                s.get("problems"),
                f"=COUNTIF({M}!$A$2:$A${mlast},$A{r})",
                f"=COUNTIFS({T}!$B$2:$B${last},$A{r},{T}!$AB$2:$AB${last},\"Ҳа\")",
                f"=COUNTIF({W}!$B$2:$B${wlast},$A{r})",
                f"=SUMIF({W}!$B$2:$B${wlast},$A{r},{W}!$H$2:$H${wlast})",
                d.budget_official, f"=O{r}-N{r}"]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=r, column=j, value=v)
    dlast = r
    _style_body(ws, 2, dlast, len(head))
    for rr in range(2, dlast + 2):
        _fmt_row(ws, rr, {3: "#,##0", 4: "#,##0", 5: "#,##0", 6: "#,##0", 7: "#,##0", 8: "#,##0",
                          9: "0.0%", 10: "#,##0", 11: "#,##0", 12: "#,##0", 13: "#,##0", 14: "#,##0.00",
                          15: "#,##0.00", 16: "#,##0.00;[Red]-#,##0.00"})
    tot = dlast + 1
    _total_row(ws, tot, len(head))
    for col in "CDEFGHJKLMNOP":
        ws[f"{col}{tot}"] = f"=SUM({col}2:{col}{dlast})"
    ws[f"I{tot}"] = f"=SUMPRODUCT(I2:I{dlast},G2:G{dlast})/G{tot}"
    ws["C1"].comment = Comment(f"Тизим ҳисоботи ({merged.report_date}): қуввати > 0, виртуал ва ГРШ "
                               "қаторларисиз барча трансформаторлар.", "Обод маҳалла")
    ws["O1"].comment = Comment("Манба: «илова 2., 138 млрд» файли, «2 илова» варағи, 5-қатор.", "Обод маҳалла")
    ws["P1"].comment = Comment("2-илова жами ва 2.1-илова манзилли рўйхати йиғиндиси орасидаги фарқ "
                               "(манбанинг ўзида).", "Обод маҳалла")
    note = ws.cell(row=tot + 2, column=1, value="Изоҳ: C–J устунлари тизим ҳисоботидан ҳисобланган қийматлар; "
                                                  "K–N устунлари бошқа варақлардан формула орқали олинади.")
    note.font = F_NOTE

    # ---------------------------------------------------------------- Тузатишлар
    ws = wb.create_sheet(S_FIX)
    head = ["ТП рақами", "Эски туман", "Эски маҳалла", "Тўғри туман", "Тўғри маҳалла", "Натижа", "Асос",
            "Обод файли: А / Б / С, В", "Тизим: А (L1) / Б (L2) / С (L3), В"]
    _table(ws, head, [12, 15, 20, 15, 22, 16, 70, 24, 28])
    rows = sorted(merged.obod_rows, key=lambda t: (RES[t.res][0], t.number))
    r = 1
    for i, t in enumerate(rows, start=1):
        r = i + 1
        new_m = t.mahalla_key[1] if t.mahalla_key else "Аниқланмаган"
        basis = (f"Туман — тизим ҳисоботидаги РЭС «{t.res}»; маҳалла — 2.1-иловада ТП-{t.base_number} шу маҳалла "
                 f"ишлари рўйхатида." if t.mahalla_key else
                 f"Туман — тизим ҳисоботидаги РЭС «{t.res}»; ТП-{t.base_number} 2.1-иловада йўқ, маҳалла аниқланмади.")
        ov = t.obod_voltages or (None, None, None)
        vals = [t.number, t.obod_district, t.obod_mahalla, RES[t.res][0], new_m,
                f"=IF(AND(B{r}=D{r},C{r}=E{r}),\"Ўзгармади\",IF(E{r}=\"Аниқланмаган\",\"Маҳалла аниқланмади\",\"Тузатилди\"))",
                basis, " / ".join(f"{v:.1f}" for v in ov if v is not None),
                " / ".join(f"{v:.1f}" if v is not None else "—" for v in (t.voltage_a, t.voltage_b, t.voltage_c))]
        for j, v in enumerate(vals, start=1):
            ws.cell(row=r, column=j, value=v)
    _style_body(ws, 2, r, len(head))
    ws.auto_filter.ref = f"A1:I{r}"

    # ---------------------------------------------------------------- Маълумот
    ws = wb.create_sheet(S_INFO, 0)
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 110
    ws["A1"] = "Обод маҳалла — бирлаштирилган маълумотлар"
    ws["A1"].font = F_TITLE
    lines = [
        ("Тузилган сана", datetime.date.today().strftime("%d.%m.%Y")),
        ("Манба 1", f"{FILES['obod']} — 205 ТП нинг техник маълумотлари (туман ва маҳалла номлари нотўғри бўлган)."),
        ("Манба 2", f"{FILES['trload']} — тизим ҳисоботи, {merged.report_date}: {len(merged.trload)} та қатор."),
        ("Манба 3", f"{FILES['program']} — 2027 йил «Обод маҳалла» дастури (2 ва 2.1-иловалар)."),
        ("Туман", "Тизим ҳисоботидаги РЭС бўйича аниқланди."),
        ("Маҳалла", "2.1-иловада маҳалла ишлари матнидаги ТП рақами (асосий рақам) бўйича, шу туман РЭСи ичида."),
        ("Обод файли", "Ҳар бир ТП тизим ҳисоботидан ТП рақами, истеъмолчилар, қувват ва кунлик истеъмол бўйича "
                       "бир маъноли топилди (205/205)."),
        ("Кучланиш", "А/Б/С фазалари тизим ҳисоботи сарлавҳалари бўйича (L1/L2/L3). Обод файлида А ва Б "
                     "устунлари ўрни алмашган — «Тузатишлар» варағида иккаласи кўрсатилган."),
        ("Ойлик / йиллик", "Ойлик = кунлик × 30, йиллик = ойлик × 12 (Обод файлидаги ҳисоблаш усули)."),
        ("Ҳисоб хатоси", "Кунлик истеъмоли манфий ёки нол ТП лар сайтдаги йиғиндиларга қўшилмайди."),
        ("Ҳолат", "ТП тоифаси юкланиш бўйича: 0–50% — яшил, 50–60% — сариқ, 60% дан юқори — қизил."),
        ("Саломатлик индекси", "0–100: кучланиш (ГОСТ 32144, 230 В ±5%), фазалар фарқи, юкланиш, "
                               "истеъмолчилар зичлиги, cos φ ва ҳисоб хатоси бўйича."),
        ("Варақлар", f"{S_DIST}, {S_MAH}, {S_TP}, {S_WORK}, {S_FIX}. Жамлар ва ҳосила устунлар формулалар билан."),
    ]
    for i, (k, v) in enumerate(lines, start=3):
        ws.cell(row=i, column=1, value=k).font = F_BOLD
        c = ws.cell(row=i, column=2, value=v)
        c.font = F_BASE
        c.alignment = Alignment(wrap_text=True, vertical="top")

    order = [S_INFO, S_DIST, S_MAH, S_TP, S_WORK, S_FIX]
    wb._sheets = [wb[n] for n in order]
    wb.active = 0
    wb.calculation.fullCalcOnLoad = True
    wb.save(path)
    return path
