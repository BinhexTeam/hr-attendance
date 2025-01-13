# Copyright 2025 Binhex - Adasat Torres de León.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

import base64
import os

from odoo.tests import new_test_user, users

from odoo.addons.base.tests.common import BaseCommon

_relative_route_ = "../static/description/icon.png"
_location_ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

_path_ = os.path.join(_location_, _relative_route_)


class TestHrAttendanceReason(BaseCommon):
    def setUp(self):
        super().setUp()

        self.user = new_test_user(
            self.env,
            login="test-user",
            groups="base.group_user,hr_attendance.group_hr_attendance_user",
        )
        self.employee = self.env["hr.employee"].create(
            {"name": self.user.login, "user_id": self.user.id}
        )

        with open(_path_, "rb") as img:
            self.img = base64.b64encode(img.read())

    @users("test-user")
    def test_user_attendance_manual(self):
        # check in
        attendance = self.env.user.employee_id.with_context(
            image=self.img
        )._attendance_action_change()
        self.assertIn(self.img, attendance.image_check_in)
        # check out
        attendance = self.env.user.employee_id.with_context(
            image=self.img
        )._attendance_action_change()
        self.assertIn(self.img, attendance.image_check_out)
