"""Сайтдан юклаб олинадиган Excel: тозаланган (такрорсиз) ишлар, ТП секциялари ва жамлар формулалар билан."""
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import District, Mahalla, ProgressEntry, Section, SourceInfo, Work
from .source import CATEGORIES

F_BASE = Font(name="Arial", size=10)
F_BOLD = Font(name="Arial", size=10, bold=True)
F_HEAD = Font(name="Arial", size=10, bold=True, color="FFFFFF")
F_TITLE = Font(name="Arial", size=13, bold=True)
F_INPUT = Font(name="Arial", size=10, color="0000FF")
FILL_HEAD = PatternFill("solid", fgColor="1F2937")
FILL_TOTAL = PatternFill("solid", fgColor="E5E7EB")
FILL_INPUT = PatternFill("solid", fgColor="FFF9C4")
FILL_STATUS = {"good": PatternFill("solid", fgColor="DCFCE7"), "warn": PatternFill("solid", fgColor="FEF3C7"),
               "crit": PatternFill("solid", fgColor="FEE2E2")}
STATUS_UZ = {"good": "Яшил", "warn": "Сариқ", "crit": "Қизил", "none": "Маълумот йўқ"}
THIN = Border(bottom=Side(style="thin", color="D1D5DB"))
NUM2 = '#,##0.00;-#,##0.00;"-"'
NUM1 = '#,##0.0;-#,##0.0;"-"'
NUM0 = '#,##0;-#,##0;"-"'
PCT = '0.0%;-0.0%;"-"'

S_INFO, S_DIST, S_MAH, S_WORK, S_TP = "Маълумот", "Туманлар", "Маҳаллалар", "Ишлар", "ТП секциялари"


def q(name):
    return f"'{name}'"


def _table(ws, head, widths):
    for i, (h, w) in enumerate(zip(head, widths), start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font, c.fill = F_HEAD, FILL_HEAD
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 42
    ws.freeze_panes = "A2"


def _row(ws, r, vals, fmts=None):
    for j, v in enumerate(vals, start=1):
        c = ws.cell(row=r, column=j, value=v)
        c.font, c.border = F_BASE, THIN
        if fmts and fmts.get(j):
            c.number_format = fmts[j]


def build_workbook():
    wb = Workbook()
    src = SourceInfo.objects.first()
    works = list(Work.objects.select_related("district", "mahalla"))
    secs = list(Section.objects.select_related("district", "mahalla", "work"))

    # ------------------------------------------------------------- Ишлар
    ws = wb.active
    ws.title = S_WORK
    head = ["Туман", "Маҳалла", "№", "Бажариладиган ишлар", "ТП (C)", "Тоифа", "Паст кучл. кабел, км",
            "Юқори кучл. кабел, км", "Жами км", "Трансформатор алмаштириш", "Янги ГКТП", "Жами трансформатор",
            "ГРШ", "Маблағ, млн сўм", "Амалда: паст кабел, км", "Амалда: юқори кабел, км", "Амалда: трансформатор",
            "Амалда: ГКТП", "Амалда: ГРШ", "Амалда: маблағ, млн сўм", "Маблағ ижроси", "Файл қаторлари"]
    _table(ws, head, [14, 18, 5, 70, 8, 26, 10, 10, 9, 11, 9, 11, 7, 12, 10, 10, 10, 9, 8, 12, 9, 11])
    ws.cell(row=1, column=15).comment = Comment("Сариқ устунлар — ижро (амалда) учун киритиладиган катаклар; "
                                                "бошланғич қиймат 0.", "Обод маҳалла")
    for i, w in enumerate(works, start=2):
        vals = [w.district.name, w.mahalla.name, w.number, w.text, w.tp_ref, CATEGORIES[w.category][0],
                w.lv_km, w.hv_km, f"=G{i}+H{i}", w.tr_upgrade, w.new_gktp, f"=J{i}+K{i}", w.grsh, w.cost,
                w.fact_lv_km, w.fact_hv_km, w.fact_tr_upgrade, w.fact_new_gktp, w.fact_grsh, w.fact_cost,
                f'=IFERROR(T{i}/N{i},"")', ", ".join(map(str, w.rows))]
        _row(ws, i, vals, {7: NUM2, 8: NUM2, 9: NUM2, 14: NUM2, 15: NUM2, 16: NUM2, 20: NUM2, 21: PCT})
        ws.cell(row=i, column=4).alignment = Alignment(wrap_text=True, vertical="top")
        for j in range(15, 21):
            ws.cell(row=i, column=j).font, ws.cell(row=i, column=j).fill = F_INPUT, FILL_INPUT
    wlast = len(works) + 1
    tot = wlast + 1
    ws.cell(row=tot, column=4, value="ЖАМИ (ҳар бир иш бир марта)").font = F_BOLD
    for j in list(range(7, 21)):
        col = get_column_letter(j)
        c = ws.cell(row=tot, column=j, value=f"=SUM({col}2:{col}{wlast})")
        c.font, c.fill, c.number_format = F_BOLD, FILL_TOTAL, NUM2
    ws.cell(row=tot, column=21, value=f'=IFERROR(T{tot}/N{tot},"")').number_format = PCT
    ws.auto_filter.ref = f"A1:V{wlast}"

    # ------------------------------------------------------------- ТП секциялари
    ws = wb.create_sheet(S_TP)
    head = ["Туман", "Маҳалла", "Иш №", "Название РЭС", "Подстанция", "Фидер", "Номер ТП", "Tr Владелец",
            "Мастер Тр", "Счётчиклар: всего", "Бытовые", "Промышленные", "Мощность, кВА", "Номер счетчика баланса",
            "Коэф. КТ", "Среднесуточное, кВт·соат", "Вчера итого, кВА", "Всего, кВА", "PF", "PF L1", "PF L2",
            "PF L3", "Ток L1, А", "Ток L2, А", "Ток L3, А", "Напряжение L1, В", "Напряжение L2, В",
            "Напряжение L3, В", "Нагрузки ТП", "Состояние счетчика", "Примечание", "Ойлик, кВт·соат",
            "Йиллик, кВт·соат", "Юкланиш (ҳисоб)", "Ҳолат", "Саломатлик индекси", "Файл қатори"]
    _table(ws, head, [13, 16, 6, 16, 24, 18, 11, 10, 9, 10, 9, 10, 10, 15, 8, 12, 10, 10, 7, 7, 7, 7, 9, 9, 9,
                      10, 10, 10, 9, 20, 30, 12, 13, 10, 10, 10, 8])
    for i, s in enumerate(secs, start=2):
        rep = s.report
        st = rep.status if s.has_data else "none"
        vals = [s.district.name, s.mahalla.name, s.work.number, s.res, s.substation, s.feeder, s.number, s.owner,
                s.master, s.consumers_total, s.consumers_household, s.consumers_commercial, s.capacity_kva,
                s.meter_no, s.ct_ratio, s.daily_kwh, s.kva_yesterday, s.kva_total, s.pf, s.pf_l1, s.pf_l2, s.pf_l3,
                s.current_a, s.current_b, s.current_c, s.voltage_a, s.voltage_b, s.voltage_c, s.load_factor,
                s.meter_state, s.note, f'=IF(P{i}="","",P{i}*30)', f'=IF(P{i}="","",P{i}*365)',
                f'=IFERROR(R{i}/M{i},"")', STATUS_UZ[st], rep.score if s.has_data else None, s.row]
        _row(ws, i, vals, {16: NUM2, 29: PCT, 32: NUM0, 33: NUM0, 34: PCT})
        ws.cell(row=i, column=35).fill = FILL_STATUS.get(st, PatternFill())
    slast = len(secs) + 1
    ws.auto_filter.ref = f"A1:AK{slast}"

    # ------------------------------------------------------------- Маҳаллалар
    ws = wb.create_sheet(S_MAH, 0)
    W, T = q(S_WORK), q(S_TP)
    head = ["Туман", "Маҳалла", "Ишлар", "Паст кабел, км", "Юқори кабел, км", "Трансформатор", "Янги ГКТП", "ГРШ",
            "Маблағ, млн сўм", "Амалда маблағ", "Ижро", "ТП секциялари", "Истеъмолчилар", "Қувват, кВА",
            "Ўртача юкланиш"]
    _table(ws, head, [14, 20, 7, 10, 10, 11, 9, 7, 13, 12, 8, 9, 12, 11, 10])
    mahs = list(Mahalla.objects.select_related("district"))
    for i, m in enumerate(mahs, start=2):
        crit = f"{W}!$A$2:$A${wlast},$A{i},{W}!$B$2:$B${wlast},$B{i}"
        tcrit = f"{T}!$A$2:$A${slast},$A{i},{T}!$B$2:$B${slast},$B{i}"
        vals = [m.district.name, m.name, f"=COUNTIFS({crit})",
                f"=SUMIFS({W}!$G$2:$G${wlast},{crit})", f"=SUMIFS({W}!$H$2:$H${wlast},{crit})",
                f"=SUMIFS({W}!$J$2:$J${wlast},{crit})", f"=SUMIFS({W}!$K$2:$K${wlast},{crit})",
                f"=SUMIFS({W}!$M$2:$M${wlast},{crit})", f"=SUMIFS({W}!$N$2:$N${wlast},{crit})",
                f"=SUMIFS({W}!$T$2:$T${wlast},{crit})", f'=IFERROR(J{i}/I{i},"")',
                f"=COUNTIFS({tcrit})", f"=SUMIFS({T}!$J$2:$J${slast},{tcrit})",
                f"=SUMIFS({T}!$M$2:$M${slast},{tcrit})",
                f'=IFERROR(SUMIFS({T}!$R$2:$R${slast},{tcrit})/N{i},"")']
        _row(ws, i, vals, {4: NUM2, 5: NUM2, 9: NUM2, 10: NUM2, 11: PCT, 13: NUM0, 14: NUM0, 15: PCT})
    mlast = len(mahs) + 1
    tot = mlast + 1
    ws.cell(row=tot, column=2, value="ЖАМИ").font = F_BOLD
    for j in range(3, 15):
        col = get_column_letter(j)
        if j == 11:
            ws.cell(row=tot, column=j, value=f'=IFERROR(J{tot}/I{tot},"")').number_format = PCT
            continue
        c = ws.cell(row=tot, column=j, value=f"=SUM({col}2:{col}{mlast})")
        c.font, c.fill, c.number_format = F_BOLD, FILL_TOTAL, NUM2
    ws.auto_filter.ref = f"A1:O{mlast}"

    # ------------------------------------------------------------- Туманлар
    ws = wb.create_sheet(S_DIST, 0)
    head = ["Туман", "РЭС", "Маҳаллалар", "Ишлар", "Паст кабел, км", "Юқори кабел, км", "Трансформатор",
            "Янги ГКТП", "ГРШ", "Маблағ, млн сўм", "Амалда маблағ", "Ижро", "ТП секциялари", "Истеъмолчилар"]
    _table(ws, head, [15, 18, 11, 8, 10, 10, 11, 9, 7, 13, 12, 8, 9, 12])
    M = q(S_MAH)
    dists = list(District.objects.all())
    for i, d in enumerate(dists, start=2):
        crit = f"{W}!$A$2:$A${wlast},$A{i}"
        vals = [d.name, d.res_name, f"=COUNTIF({M}!$A$2:$A${mlast},$A{i})", f"=COUNTIF({crit})",
                f"=SUMIF({crit},{W}!$G$2:$G${wlast})", f"=SUMIF({crit},{W}!$H$2:$H${wlast})",
                f"=SUMIF({crit},{W}!$J$2:$J${wlast})", f"=SUMIF({crit},{W}!$K$2:$K${wlast})",
                f"=SUMIF({crit},{W}!$M$2:$M${wlast})", f"=SUMIF({crit},{W}!$N$2:$N${wlast})",
                f"=SUMIF({crit},{W}!$T$2:$T${wlast})", f'=IFERROR(K{i}/J{i},"")',
                f"=COUNTIF({T}!$A$2:$A${slast},$A{i})",
                f"=SUMIF({T}!$A$2:$A${slast},$A{i},{T}!$J$2:$J${slast})"]
        _row(ws, i, vals, {5: NUM2, 6: NUM2, 10: NUM2, 11: NUM2, 12: PCT, 14: NUM0})
    dlast = len(dists) + 1
    tot = dlast + 1
    ws.cell(row=tot, column=1, value="ЖАМИ").font = F_BOLD
    for j in range(3, 15):
        col = get_column_letter(j)
        if j == 12:
            ws.cell(row=tot, column=j, value=f'=IFERROR(K{tot}/J{tot},"")').number_format = PCT
            continue
        c = ws.cell(row=tot, column=j, value=f"=SUM({col}2:{col}{dlast})")
        c.font, c.fill, c.number_format = F_BOLD, FILL_TOTAL, NUM2

    # ------------------------------------------------------------- Ижро журнали
    ws = wb.create_sheet("Ижро журнали")
    _table(ws, ["Сана", "Туман", "Маҳалла", "Иш №", "Иш", "Паст кабел, км", "Юқори кабел, км", "Трансформатор",
                "Янги ГКТП", "ГРШ", "Маблағ, млн сўм", "Изоҳ", "Киритилган вақт"],
           [11, 14, 18, 7, 50, 10, 10, 11, 9, 7, 12, 40, 17])
    dname = {d.order: d.name for d in dists}
    entries = list(ProgressEntry.objects.select_related("work__mahalla"))
    for i, e in enumerate(entries, start=2):
        _row(ws, i, [e.date, dname.get(e.district_order, ""), e.work.mahalla.name if e.work else "", e.number,
                     e.work_title, e.lv_km, e.hv_km, e.tr_upgrade, e.new_gktp, e.grsh, e.cost, e.note,
                     timezone.localtime(e.created_at).replace(tzinfo=None)],
             {1: "DD.MM.YYYY", 11: NUM2, 13: "DD.MM.YYYY HH:MM"})
    if entries:
        tot = len(entries) + 2
        ws.cell(row=tot, column=5, value="ЖАМИ").font = F_BOLD
        for j in range(6, 12):
            col = get_column_letter(j)
            c = ws.cell(row=tot, column=j, value=f"=SUM({col}2:{col}{tot - 1})")
            c.font, c.fill, c.number_format = F_BOLD, FILL_TOTAL, NUM2

    # ------------------------------------------------------------- Маълумот
    ws = wb.create_sheet(S_INFO, 0)
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 110
    ws["A1"] = "«Обод маҳалла» 2027 — электр таъминоти манзилли дастури (тозаланган маълумотлар)"
    ws["A1"].font = F_TITLE
    lines = [
        ("Манба", f"{src.file_name if src else ''}, варақ «{src.sheet if src else ''}»"),
        ("Ҳисоблаш", "Манба файлда бир иш ТП секциялари бўйича бир неча қаторда такрорланган — бу ерда ҳар бир иш "
                     "бир марта ҳисобланган. Матни рақамларга мос келмаган қаторлар рақамлар бўйича тузатилган, "
                     "манфий истеъмол ва бўш ТП маълумотлари олинмаган."),
        ("Ижро (амалда)", "«Ишлар» варағидаги сариқ устунлар — сайтдаги админ панелида киритилган ижро журнали "
                          "йиғиндиси; ҳар бир ёзув «Ижро журнали» варағида."),
        ("ТП ҳолати", "Юкланиш бўйича: 0–50% — яшил, 50–60% — сариқ, 60% дан юқори — қизил."),
        ("Ойлик / йиллик", "Ойлик = кунлик × 30, йиллик = кунлик × 365 (ҳисобланган)."),
        ("Кучланиш", "Файл сарлавҳасида кучланиш устунлари L2, L1, L3 тартибида; бу ерда L1, L2, L3 тартибида."),
    ] + [("Изоҳ", n) for n in (src.notes if src else [])]
    for i, (k, v) in enumerate(lines, start=3):
        ws.cell(row=i, column=1, value=k).font = F_BOLD
        c = ws.cell(row=i, column=2, value=v)
        c.font = F_BASE
        c.alignment = Alignment(wrap_text=True, vertical="top")

    wb.calculation.fullCalcOnLoad = True
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
