from odoo import _, fields, models
from odoo.exceptions import ValidationError


class HrAttendanceReportWizard(models.TransientModel):
    _name = "hr.attendance.report.wizard"
    _description = "Hr Attendance Report Wizard"

    report_type = fields.Selection(
        selection=[
            ("individual", "By employee"),
            ("department", "By department"),
        ],
        string="Type of report",
        required=True,
        default="individual",
    )

    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Employee",
    )

    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Department",
    )

    date_from = fields.Date(
        string="Start date",
        required=True,
    )

    date_to = fields.Date(
        string="End date",
        required=True,
    )

    detailed = fields.Boolean(
        string="Detailed report",
        default=False,
        help="if enabled, the report will show each attendance record. "
        "Otherwise, it will show a summary per day.",
    )

    include_open_attendances = fields.Boolean(
        string="Include open attendances",
        default=False,
        help="Includes records without check_out. Duration will not be calculated for them.",
    )

    include_empty_days = fields.Boolean(
        string="Include empty days",
        default=False,
        help="Only applies in summary mode. Shows all days in the range "
        "even if there are no attendance records.",
    )
    time_format = fields.Selection(
        selection=[
            ("hhmm", "hh:mm"),
            ("decimal", "Decimal"),
        ],
        string="Hours format",
        required=True,
        default="hhmm",
    )

    def _validate(self):
        self.ensure_one()
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError(_("Start date cannot be after end date."))
        if self.report_type == "individual" and not self.employee_id:
            raise ValidationError(
                _("You must select an employee for the individual report.")
            )
        if self.report_type == "department" and not self.department_id:
            raise ValidationError(
                _("You must select a department for the department report.")
            )

    def action_print_report(self):
        self.ensure_one()
        self._validate()
        data = {
            "report_type": self.report_type,
            "employee_id": self.employee_id.id,
            "department_id": self.department_id.id or self.employee_id.department_id.id,
            "company_id": self.employee_id.company_id.id
            if self.employee_id
            else self.env.company.id,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "detailed": self.detailed,
            "include_open_attendances": self.include_open_attendances,
            "include_empty_days": self.include_empty_days,
            "time_format": self.time_format,
        }
        return (
            self.env.ref("hr_attendance_report.action_report_attendance")
            .with_context(tz=self.env.user.tz)
            .report_action(self, data)
        )

    # def _get_report_data(self):
    #     """
    #     Delega al servicio interno la construcción de los datos del informe.
    #     Devuelve un dict listo para pasar al template QWeb.
    #     """
    #     self.ensure_one()
    #     service = self.env["hr.attendance.report.service"]
    #     return service.get_report_data(self)
