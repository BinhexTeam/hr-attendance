from datetime import datetime, timedelta

from odoo import _, models


class HrAttendanceReport(models.AbstractModel):
    _name = "report.hr_attendance_report.report_attendance_template"
    _description = "Report Attendance"

    def _get_totals(self, data, lines):
        if data["report_type"] == "individual":
            return {
                "total_worked_hours": sum(line["worked_hours"] for line in lines),
                "total_attendances": len([line for line in lines if line["check_in"]]),
                "total_days": len([line for line in lines if line["worked_hours"] > 0]),
                "time_format": data["time_format"],
            }
        else:
            return {
                "total_workcenter_hours": sum(
                    line["total_worked_hours"] for line in lines
                ),
                "total_employees": len(lines),
                "total_attendances": sum(len(line["attendances"]) for line in lines),
                "time_format": data["time_format"],
            }

    def _get_report_values(self, docids, data=None):
        if data["report_type"] == "individual":
            docs, lines = self._get_attendance_by_employee(data)
            totals = self._get_totals(data, lines)
        else:
            docs, lines = self._get_attendance_by_department(data)
            totals = self._get_totals(data, lines)

        data = self._update_data_values(data)
        return {
            "doc_ids": docids,
            "doc_model": "hr.attendance",
            "docs": docs,
            "lines": lines,
            "totals": totals,
            "datas": data,
            "tz": self.env.user.tz,
        }

    def _update_data_values(self, data):
        employee = self.env["hr.employee"]
        department = self.env["hr.department"]
        company = self.env["res.company"]
        data.update(
            {
                "employee_id": employee.browse(data["employee_id"]),
                "department_id": department.browse(data["department_id"]),
                "company_id": company.browse(data["company_id"]),
            }
        )
        return data

    def _get_attendance_by_employee(self, data):
        hr_attendance = self.env["hr.attendance"]
        query = """
            SELECT
                att.id
            FROM hr_attendance att
            JOIN hr_employee emp ON emp.id = att.employee_id
            WHERE att.employee_id = %s
              AND att.check_in::date >= %s
              AND att.check_out::date <= %s
            ORDER BY att.check_in ASC;
        """
        if data["include_open_attendances"]:
            query = query.replace(
                "att.check_out::date <= %s",
                "(att.check_out::date <= %s OR att.check_out IS NULL)",
            )
        params = (data["employee_id"], data["date_from"], data["date_to"])
        self._cr.execute(query, params)
        ids = [row[0] for row in self._cr.fetchall()]
        attendance_ids = hr_attendance.browse(ids)
        attendances = []
        if not data["detailed"]:
            groups = {}
            if data["include_empty_days"]:
                current_date = datetime.strptime(data["date_from"], "%Y-%m-%d").date()
                date_to = datetime.strptime(data["date_to"], "%Y-%m-%d").date()

                while current_date <= date_to:
                    groups.setdefault(current_date, [])
                    current_date += timedelta(days=1)

            for attendance in attendance_ids:
                date = attendance.check_in.date()
                groups.setdefault(date, [])
                groups[date].append(attendance)

            for group, att in groups.items():
                if not att:
                    att = [hr_attendance]
                attendances.append(
                    {
                        "date": group,
                        "check_in": min(a.check_in for a in att),
                        "check_out": max(a.check_out for a in att),
                        "worked_hours": sum(a.worked_hours for a in att) or 0,
                        "state": (
                            _("Open")
                            if (att[0].check_in and not att[-1].check_out)
                            else _("Closed")
                        ),
                    }
                )
            return attendance_ids, attendances

        for attendance in attendance_ids:
            attendances.append(
                {
                    "date": attendance.check_in.date().strftime("%d/%m/%Y"),
                    "check_in": attendance.check_in,
                    "check_out": attendance.check_out,
                    "worked_hours": attendance.worked_hours,
                    "state": _("Open") if not attendance.check_out else _("Closed"),
                }
            )
        return attendance_ids, attendances

    def _get_attendance_by_department(self, data):
        hr_attendance = self.env["hr.attendance"]
        query = """
            SELECT
                e.name                      AS employee_name,
                ARRAY_AGG(att.id) AS attendances,
                SUM(att.worked_hours)         AS total_worked_hours,
                COUNT(att.id)                 AS total_records
            FROM hr_attendance att
            JOIN hr_employee e ON e.id = att.employee_id
            WHERE e.department_id = %s
                AND att.check_in::date >= %s
                AND att.check_out::date <= %s
            GROUP BY e.id, e.name
            ORDER BY e.name DESC;
        """

        self.env.cr.execute(
            query, (data["department_id"], data["date_from"], data["date_to"])
        )
        attendances = self.env.cr.dictfetchall()
        worked_days = set()
        for line in attendances:
            for att in line["attendances"]:
                attendance = hr_attendance.browse(att)
                date = attendance.check_in.date()
                worked_days.add(date)
            line.update(
                {
                    "worked_days": len(worked_days),
                }
            )

        return hr_attendance, attendances
