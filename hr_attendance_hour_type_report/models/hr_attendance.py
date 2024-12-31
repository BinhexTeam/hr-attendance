# Copyright 2021 Camptocamp SA
# Copyright 2024 Binhex - Adasat Torres de León
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import datetime as dt
import logging

import pytz

from odoo import _, api, exceptions, fields, models

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    worked_hours_nighttime = fields.Float(
        string="Night hours", compute="_compute_worked_hours", store=True
    )
    worked_hours_daytime = fields.Float(
        string="Day hours",
        compute="_compute_worked_hours",
        store=True,
        readonly=True,
    )

    worked_hours_overtime = fields.Float(
        string="Overtime hours",
        compute="_compute_worked_hours",
        store=True,
        readonly=True,
    )

    date = fields.Date(
        help="date of the attendance, from the payroll point of view",
        compute="_compute_date",
        store=True,
    )
    date_type = fields.Selection(
        [("normal", "Weekday"), ("sunday", "Sunday"), ("holiday", "Public Holiday")],
        compute="_compute_date_type",
        store=True,
    )

    company_id = fields.Many2one(
        comodel_name="res.company",
        default=lambda self: self.env.company,
    )

    hr_attendance_overtime = fields.Boolean(related="company_id.hr_attendance_overtime")

    allow_weighting_nighttime_hours = fields.Boolean(
        related="company_id.allow_weighting_nighttime_hours"
    )

    allow_weighting_overtime_hours = fields.Boolean(
        related="company_id.allow_weighting_overtime_hours"
    )

    weighting_worked_nighttime_hours = fields.Float(
        compute="_compute_weighting_hours",
        store=True,
    )
    weighting_worked_overtime_hours = fields.Float(
        compute="_compute_weighting_hours",
        store=True,
    )

    @api.depends(
        "company_id.weighting_nighttime_hours", "company_id.weighting_overtime_hours"
    )
    def _compute_weighting_hours(self):
        for rec in self:
            nighttime_hours = rec.worked_hours_nighttime
            overtime_hours = rec.worked_hours_overtime
            if rec.allow_weighting_nighttime_hours:
                nighttime_hours *= rec.company_id.weighting_nighttime_hours
            if rec.allow_weighting_overtime_hours:
                overtime_hours *= rec.company_id.weighting_overtime_hours
            rec.weighting_worked_nighttime_hours = nighttime_hours
            rec.weighting_worked_overtime_hours = overtime_hours

    @api.depends("date")
    def _compute_date_type(self):
        for rec in self:
            if rec.date.weekday() == 6:
                rec.date_type = "sunday"
            elif self.env["hr.holidays.public"].is_public_holiday(
                rec.date, rec.employee_id.id
            ):
                rec.date_type = "holiday"
            else:
                rec.date_type = "normal"

    @api.depends("check_in")
    def _compute_date(self):
        for rec in self:
            TZ = pytz.timezone(rec.employee_id.tz)
            tz = rec.employee_id.tz
            check_in = rec.check_in
            if not check_in.tzinfo:
                check_in = TZ.localize(check_in)
            check_in_tz = check_in.astimezone(pytz.timezone(tz))
            rec.date = check_in_tz.date()

    @api.depends("check_in", "check_out")
    def _compute_worked_hours(self):
        super()._compute_worked_hours()

        for rec in self:
            TZ = pytz.timezone(rec.employee_id.tz)
            rec.worked_hours_nighttime = 0
            rec.worked_hours_daytime = 0
            if not rec.check_out:
                continue
            if rec.worked_hours > 24:
                raise exceptions.UserError(
                    _("More than 24h of work in 1 shift is forbidden")
                )
            night_start = rec.employee_id.company_id.hr_night_work_hour_start
            hour_night_start = int(night_start)
            minute_night_start = int(60 * (night_start - hour_night_start))
            night_end = rec.employee_id.company_id.hr_night_work_hour_end
            hour_night_end = int(night_end)
            minute_night_end = int(60 * (night_end - hour_night_end))
            tz = pytz.timezone(rec.employee_id.tz)
            check_in = TZ.localize(rec.check_in)
            check_out = TZ.localize(rec.check_out)
            curr_day_night_start = tz.localize(
                dt.datetime.combine(
                    rec.date, dt.time(hour=hour_night_start, minute=minute_night_start)
                )
            ).astimezone(TZ)
            curr_day_night_end = tz.localize(
                dt.datetime.combine(
                    rec.date, dt.time(hour=hour_night_end, minute=minute_night_end)
                )
            ).astimezone(TZ)
            next_day_night_start = tz.localize(
                dt.datetime.combine(
                    rec.date + dt.timedelta(days=1),
                    dt.time(hour=hour_night_start, minute=minute_night_start),
                )
            ).astimezone(TZ)
            next_day_night_end = tz.localize(
                dt.datetime.combine(
                    rec.date + dt.timedelta(days=1),
                    dt.time(hour=hour_night_end, minute=minute_night_end),
                )
            ).astimezone(TZ)
            rec.worked_hours_nighttime += (
                min(check_out, curr_day_night_end) - min(curr_day_night_end, check_in)
            ).total_seconds() / 3600.0
            if check_out > curr_day_night_start:
                rec.worked_hours_nighttime += (
                    min(check_out, next_day_night_end)
                    - max(check_in, curr_day_night_start)
                ).total_seconds() / 3600.0
            rec.worked_hours_nighttime += (
                max(check_out, next_day_night_start) - next_day_night_start
            ).total_seconds() / 3600.0
            if check_out > next_day_night_start:
                _logger.warning("very long_shift for employee %s" % rec.employee_id.id)
            rec.worked_hours_daytime = rec.worked_hours - rec.worked_hours_nighttime
            if (
                rec.hr_attendance_overtime
                and rec.employee_id.resource_calendar_id
                and rec.worked_hours
                > rec.employee_id.resource_calendar_id.hours_per_day
            ):
                rec.worked_hours_overtime = (
                    rec.worked_hours
                    - rec.employee_id.resource_calendar_id.hours_per_day
                )
            else:
                rec.worked_hours_overtime = 0
        return
