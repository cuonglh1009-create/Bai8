#/****************/
# File test cho bai8.py (Delegate & Event)
# Chạy:  python -m unittest test_bai8 -v
# Đặt cùng thư mục với bai8.py
#/****************/

import inspect
import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime

from bai8 import (
    DeviceStatus, AlertSeverity,
    DeviceStatusChangedEventArgs, DeviceAlertEventArgs,
    InvalidDeviceReadingException,
    TeachingDevice, ProjectorRemote, AirConditionerRemote, WirelessMicrophone,
    ConsoleNotificationService, DeviceAuditLogger, MaintenanceService,
    FilteredAlertSubscriber, DeviceMonitoringCoordinator,
)

W = AlertSeverity.WARNING
C = AlertSeverity.CRITICAL


# ======================================================================
#  CÔNG CỤ DÙNG CHUNG
# ======================================================================
class Recorder:
    """Subscriber giả: ghi lại mọi lần được gọi (sender, e)."""

    def __init__(self):
        self.calls = []

    def __call__(self, sender, e):
        self.calls.append((sender, e))

    @property
    def events(self):
        return [e for _, e in self.calls]

    def severities(self):
        return [e.severity for e in self.events]


class QuietTestCase(unittest.TestCase):
    """Chặn print() của chương trình để kết quả test gọn; đọc lại qua self.printed."""

    def setUp(self):
        self._buf = io.StringIO()
        cm = redirect_stdout(self._buf)
        cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)

    @property
    def printed(self):
        return self._buf.getvalue()


def make_projector(level=90):
    return ProjectorRemote("PRJ01", "Epson", level)


def make_ac():
    return AirConditionerRemote("AC01", "Daikin", "P.101")


def make_mic(battery=70, signal=85):
    return WirelessMicrophone("MIC01", "Shure", battery, signal)


def watch_alerts(device):
    rec = Recorder()
    device.add_alert_raised_handler(rec)
    return rec


def make_alert(severity, device_id="AC01", message="msg"):
    return DeviceAlertEventArgs(device_id, message, severity, datetime.now())


# ======================================================================
#  1. PUBLISHER: ĐĂNG KÝ / HỦY / PHÁT EVENT TRẠNG THÁI
# ======================================================================
class TestPublisherStatusEvent(QuietTestCase):
    def setUp(self):
        super().setUp()
        self.dev = make_ac()

    def test_trang_thai_mac_dinh_la_available(self):
        """Thiết bị mới tạo có trạng thái Available"""
        self.assertEqual(self.dev.status, DeviceStatus.AVAILABLE)

    def test_doi_trang_thai_phat_event_dung_du_lieu(self):
        """Đổi trạng thái -> StatusChanged mang đúng id, old, new, thời điểm"""
        rec = Recorder()
        self.dev.add_status_changed_handler(rec)
        self.dev.change_status(DeviceStatus.BORROWED)
        self.assertEqual(len(rec.calls), 1)
        sender, e = rec.calls[0]
        self.assertIs(sender, self.dev)
        self.assertIsInstance(e, DeviceStatusChangedEventArgs)
        self.assertEqual(e.device_id, "AC01")
        self.assertEqual(e.old_status, DeviceStatus.AVAILABLE)
        self.assertEqual(e.new_status, DeviceStatus.BORROWED)
        self.assertIsInstance(e.changed_at, datetime)

    def test_status_duoc_cap_nhat_truoc_khi_phat_event(self):
        """Phải cập nhật Status rồi mới phát event (handler thấy trạng thái mới)"""
        seen = []
        self.dev.add_status_changed_handler(lambda s, e: seen.append(s.status))
        self.dev.change_status(DeviceStatus.UNDER_MAINTENANCE)
        self.assertEqual(seen, [DeviceStatus.UNDER_MAINTENANCE])

    def test_cung_trang_thai_khong_phat_event(self):
        """ChangeStatus với trạng thái trùng -> không phát event"""
        rec = Recorder()
        self.dev.add_status_changed_handler(rec)
        self.dev.change_status(DeviceStatus.AVAILABLE)
        self.assertEqual(rec.calls, [])

    def test_doi_qua_lai_phat_dung_so_event(self):
        """Available -> Borrowed -> Borrowed -> Available: chỉ 2 event"""
        rec = Recorder()
        self.dev.add_status_changed_handler(rec)
        self.dev.change_status(DeviceStatus.BORROWED)
        self.dev.change_status(DeviceStatus.BORROWED)
        self.dev.change_status(DeviceStatus.AVAILABLE)
        self.assertEqual(len(rec.calls), 2)
        self.assertEqual(rec.events[1].old_status, DeviceStatus.BORROWED)
        self.assertEqual(rec.events[1].new_status, DeviceStatus.AVAILABLE)

    def test_nhieu_subscriber_cung_nhan_event(self):
        """Một event có nhiều subscriber"""
        a, b = Recorder(), Recorder()
        self.dev.add_status_changed_handler(a)
        self.dev.add_status_changed_handler(b)
        self.dev.change_status(DeviceStatus.BORROWED)
        self.assertEqual(len(a.calls), 1)
        self.assertEqual(len(b.calls), 1)

    def test_huy_dang_ky_thi_khong_nhan_nua(self):
        """Sau khi hủy đăng ký, subscriber không nhận event nữa"""
        rec = Recorder()
        self.dev.add_status_changed_handler(rec)
        self.dev.remove_status_changed_handler(rec)
        self.dev.change_status(DeviceStatus.BORROWED)
        self.assertEqual(rec.calls, [])

    def test_dang_ky_trung_chi_nhan_mot_lan(self):
        """Đăng ký cùng handler hai lần -> chỉ được gọi một lần"""
        rec = Recorder()
        self.dev.add_status_changed_handler(rec)
        self.dev.add_status_changed_handler(rec)
        self.dev.change_status(DeviceStatus.BORROWED)
        self.assertEqual(len(rec.calls), 1)

    def test_huy_handler_chua_dang_ky_khong_loi(self):
        """Hủy một handler chưa từng đăng ký không gây lỗi"""
        self.dev.remove_status_changed_handler(Recorder())
        self.dev.remove_alert_raised_handler(Recorder())

    def test_handler_tu_huy_khi_dang_chay_khong_lam_bo_sot_handler_khac(self):
        """Handler tự gỡ mình giữa chừng: handler đứng sau vẫn phải được gọi"""
        order = []

        def first(sender, e):
            order.append("first")
            self.dev.remove_status_changed_handler(first)

        def second(sender, e):
            order.append("second")

        self.dev.add_status_changed_handler(first)
        self.dev.add_status_changed_handler(second)
        self.dev.change_status(DeviceStatus.BORROWED)
        self.assertEqual(order, ["first", "second"])


# ======================================================================
#  2. PUBLISHER: QUY TẮC THIẾT KẾ
# ======================================================================
class TestPublisherDesignRules(QuietTestCase):
    def test_ben_ngoai_khong_co_ham_phat_event_cong_khai(self):
        """Mã bên ngoài không được tự phát sinh event (không có hàm raise/on công khai)"""
        dev = make_ac()
        for name in ("raise_alert", "rasie_alert", "on_status_changed", "on_alert_raised"):
            self.assertFalse(hasattr(dev, name), f"'{name}' không được là hàm công khai")

    def test_publisher_khong_tham_chieu_truc_tiep_subscriber(self):
        """TeachingDevice không được biết logger / bảo trì / giao diện"""
        src = inspect.getsource(TeachingDevice)
        for name in ("MaintenanceService", "DeviceAuditLogger",
                     "ConsoleNotificationService", "print(", "input("):
            self.assertNotIn(name, src)

    def test_them_subscriber_moi_khong_can_sua_publisher(self):
        """Subscriber tự viết (không thuộc đề) vẫn nhận được event"""
        got = []
        dev = make_projector()
        dev.add_alert_raised_handler(lambda s, e: got.append(e.message))
        dev.update_battery_level(10)
        self.assertEqual(len(got), 1)

    def test_id_hoac_name_rong_bi_tu_choi(self):
        """Id hoặc Name rỗng -> ValueError"""
        with self.assertRaises(ValueError):
            AirConditionerRemote("", "Daikin", "P.101")
        with self.assertRaises(ValueError):
            AirConditionerRemote("AC01", "", "P.101")


# ======================================================================
#  3. PROJECTOR REMOTE
# ======================================================================
class TestProjectorRemote(QuietTestCase):
    def test_pin_khoi_tao_ngoai_khoang_nem_ngoai_le(self):
        """Pin ngoài 0-100 khi tạo -> InvalidDeviceReadingException"""
        for bad in (-1, 101):
            with self.assertRaises(InvalidDeviceReadingException) as ctx:
                ProjectorRemote("PRJ01", "Epson", bad)
            self.assertEqual(ctx.exception.device_id, "PRJ01")
            self.assertEqual(ctx.exception.invalid_value, bad)

    def test_cap_nhat_ngoai_khoang_nem_ngoai_le_va_giu_nguyen_gia_tri(self):
        """Cập nhật pin sai -> ném ngoại lệ, pin cũ giữ nguyên, không phát cảnh báo"""
        p = make_projector(50)
        rec = watch_alerts(p)
        for bad in (-5, 150):
            with self.assertRaises(InvalidDeviceReadingException) as ctx:
                p.update_battery_level(bad)
            self.assertEqual(ctx.exception.device_id, "PRJ01")
            self.assertEqual(ctx.exception.invalid_value, bad)
        self.assertEqual(p.battery_level, 50)
        self.assertEqual(rec.calls, [])

    def test_gia_tri_bien_0_va_100_hop_le(self):
        """0 và 100 là giá trị hợp lệ"""
        p = make_projector(50)
        p.update_battery_level(100)
        self.assertEqual(p.battery_level, 100)
        p.update_battery_level(0)
        self.assertEqual(p.battery_level, 0)

    def test_pin_duoi_20_phat_warning(self):
        """Pin xuống dưới 20% -> Warning (19)"""
        p = make_projector(90)
        rec = watch_alerts(p)
        p.update_battery_level(19)
        self.assertEqual(rec.severities(), [W])

    def test_pin_dung_20_khong_canh_bao(self):
        """Pin = 20% chưa phải 'dưới 20%' -> không cảnh báo"""
        p = make_projector(90)
        rec = watch_alerts(p)
        p.update_battery_level(20)
        self.assertEqual(rec.calls, [])

    def test_pin_thap_nhung_khac_0_la_warning_khong_phai_critical(self):
        """Pin 5% (hoặc 1%) vẫn chỉ là Warning; Critical chỉ khi bằng 0"""
        for level in (5, 1):
            p = make_projector(90)
            rec = watch_alerts(p)
            p.update_battery_level(level)
            self.assertEqual(rec.severities(), [W], f"level={level}")

    def test_pin_ve_0_phat_critical(self):
        """Pin = 0% -> Critical"""
        p = make_projector(90)
        rec = watch_alerts(p)
        p.update_battery_level(0)
        self.assertEqual(rec.severities(), [C])

    def test_kich_ban_90_15_12_0(self):
        """90 -> 15 -> 12 -> 0: đúng 2 cảnh báo (Warning rồi Critical), không lặp ở 12"""
        p = make_projector(90)
        rec = watch_alerts(p)
        for level in (15, 12, 0):
            p.update_battery_level(level)
        self.assertEqual(rec.severities(), [W, C])

    def test_cung_vung_warning_khong_phat_lai(self):
        """Cập nhật pin nhưng vẫn cùng vùng Warning -> không cảnh báo thêm"""
        p = make_projector(90)
        rec = watch_alerts(p)
        for level in (19, 15, 10, 1):
            p.update_battery_level(level)
        self.assertEqual(rec.severities(), [W])

    def test_pin_0_lap_lai_khong_phat_lai(self):
        """Đã ở 0% mà cập nhật 0% nữa -> không phát lại Critical"""
        p = make_projector(90)
        rec = watch_alerts(p)
        p.update_battery_level(0)
        p.update_battery_level(0)
        self.assertEqual(rec.severities(), [C])

    def test_phuc_hoi_khong_phat_canh_bao(self):
        """Pin tăng lại vùng an toàn -> không cảnh báo"""
        p = make_projector(90)
        rec = watch_alerts(p)
        p.update_battery_level(0)
        p.update_battery_level(60)
        self.assertEqual(rec.severities(), [C])

    def test_tut_lai_sau_khi_phuc_hoi_phat_lai(self):
        """Tụt xuống thấp lần 2 sau khi đã phục hồi -> cảnh báo lại"""
        p = make_projector(90)
        rec = watch_alerts(p)
        p.update_battery_level(15)
        p.update_battery_level(80)
        p.update_battery_level(15)
        self.assertEqual(rec.severities(), [W, W])

    def test_canh_bao_co_day_du_du_lieu(self):
        """DeviceAlertEventArgs có id, message, severity, thời điểm"""
        p = make_projector(90)
        rec = watch_alerts(p)
        p.update_battery_level(10)
        e = rec.events[0]
        self.assertIsInstance(e, DeviceAlertEventArgs)
        self.assertEqual(e.device_id, "PRJ01")
        self.assertTrue(isinstance(e.message, str) and e.message.strip())
        self.assertIsInstance(e.occurred_at, datetime)

    def test_khoi_tao_pin_thap_khong_phat_canh_bao(self):
        """Khởi tạo không có subscriber nên không thể phát cảnh báo; không lỗi"""
        p = make_projector(5)
        self.assertEqual(p.battery_level, 5)


# ======================================================================
#  4. AIR CONDITIONER REMOTE
# ======================================================================
class TestAirConditionerRemote(QuietTestCase):
    def test_thuoc_tinh_ban_dau(self):
        """AssignedRoom đúng và ban đầu IsResponsive = True"""
        ac = make_ac()
        self.assertEqual(ac.assigned_room, "P.101")
        self.assertTrue(ac.is_responsive)

    def test_mat_phan_hoi_phat_critical(self):
        """Phản hồi -> không phản hồi: cảnh báo Critical"""
        ac = make_ac()
        rec = watch_alerts(ac)
        ac.update_response_state(False)
        self.assertEqual(rec.severities(), [C])
        self.assertFalse(ac.is_responsive)
        self.assertEqual(rec.events[0].device_id, "AC01")

    def test_khong_phan_hoi_lap_lai_khong_phat_lai(self):
        """Đã không phản hồi mà báo tiếp 'không phản hồi' -> không phát lặp"""
        ac = make_ac()
        rec = watch_alerts(ac)
        ac.update_response_state(False)
        ac.update_response_state(False)
        ac.update_response_state(False)
        self.assertEqual(len(rec.calls), 1)

    def test_dang_phan_hoi_goi_true_khong_phat(self):
        """Đang phản hồi mà gọi True -> không cảnh báo"""
        ac = make_ac()
        rec = watch_alerts(ac)
        ac.update_response_state(True)
        self.assertEqual(rec.calls, [])

    def test_phuc_hoi_khong_phat(self):
        """Không phản hồi -> phản hồi: không cảnh báo"""
        ac = make_ac()
        ac.update_response_state(False)
        rec = watch_alerts(ac)
        ac.update_response_state(True)
        self.assertEqual(rec.calls, [])
        self.assertTrue(ac.is_responsive)

    def test_mat_phan_hoi_lan_hai_sau_phuc_hoi_phat_lai(self):
        """Mất phản hồi -> phục hồi -> mất lại: phát Critical lần nữa"""
        ac = make_ac()
        rec = watch_alerts(ac)
        ac.update_response_state(False)
        ac.update_response_state(True)
        ac.update_response_state(False)
        self.assertEqual(rec.severities(), [C, C])


# ======================================================================
#  5. WIRELESS MICROPHONE
# ======================================================================
class TestWirelessMicrophone(QuietTestCase):
    def test_khoi_tao_ngoai_khoang_nem_ngoai_le(self):
        """Pin hoặc tín hiệu ngoài 0-100 khi tạo -> ngoại lệ"""
        with self.assertRaises(InvalidDeviceReadingException) as ctx:
            WirelessMicrophone("MIC01", "Shure", 101, 50)
        self.assertEqual(ctx.exception.invalid_value, 101)
        with self.assertRaises(InvalidDeviceReadingException) as ctx:
            WirelessMicrophone("MIC01", "Shure", 50, -1)
        self.assertEqual(ctx.exception.invalid_value, -1)

    def test_cap_nhat_ngoai_khoang_nem_ngoai_le_va_giu_nguyen(self):
        """Cập nhật pin/tín hiệu sai -> ngoại lệ, giá trị cũ giữ nguyên"""
        m = make_mic(70, 85)
        rec = watch_alerts(m)
        with self.assertRaises(InvalidDeviceReadingException):
            m.update_battery_level(101)
        with self.assertRaises(InvalidDeviceReadingException):
            m.update_signal_quality(-1)
        self.assertEqual(m.battery_level, 70)
        self.assertEqual(m.signal_quality, 85)
        self.assertEqual(rec.calls, [])

    def test_gia_tri_doc_duoc_qua_property(self):
        """battery_level và signal_quality phản ánh giá trị mới"""
        m = make_mic(70, 85)
        m.update_battery_level(55)
        m.update_signal_quality(60)
        self.assertEqual(m.battery_level, 55)
        self.assertEqual(m.signal_quality, 60)

    # --- Pin ---
    def test_pin_duoi_30_phat_warning(self):
        """Pin 29% -> Warning"""
        m = make_mic()
        rec = watch_alerts(m)
        m.update_battery_level(29)
        self.assertEqual(rec.severities(), [W])

    def test_pin_dung_30_khong_canh_bao(self):
        """Pin 30% -> không cảnh báo"""
        m = make_mic()
        rec = watch_alerts(m)
        m.update_battery_level(30)
        self.assertEqual(rec.calls, [])

    def test_pin_0_phat_critical(self):
        """Pin 0% -> Critical"""
        m = make_mic()
        rec = watch_alerts(m)
        m.update_battery_level(0)
        self.assertEqual(rec.severities(), [C])

    def test_pin_cung_vung_khong_phat_lai(self):
        """Pin 25 -> 20 -> 5: cùng vùng Warning nên chỉ 1 cảnh báo; rồi 0 -> thêm Critical"""
        m = make_mic()
        rec = watch_alerts(m)
        for level in (25, 20, 5):
            m.update_battery_level(level)
        self.assertEqual(rec.severities(), [W])
        m.update_battery_level(0)
        self.assertEqual(rec.severities(), [W, C])

    # --- Tín hiệu ---
    def test_tin_hieu_duoi_40_phat_warning(self):
        """Tín hiệu 39% -> Warning"""
        m = make_mic()
        rec = watch_alerts(m)
        m.update_signal_quality(39)
        self.assertEqual(rec.severities(), [W])

    def test_tin_hieu_dung_40_khong_canh_bao(self):
        """Tín hiệu 40% -> không cảnh báo"""
        m = make_mic()
        rec = watch_alerts(m)
        m.update_signal_quality(40)
        self.assertEqual(rec.calls, [])

    def test_tin_hieu_0_phat_critical(self):
        """Tín hiệu 0% -> Critical"""
        m = make_mic()
        rec = watch_alerts(m)
        m.update_signal_quality(0)
        self.assertEqual(rec.severities(), [C])

    def test_tin_hieu_cung_vung_khong_phat_lai(self):
        """Tín hiệu 35 -> 20 -> 5: chỉ 1 Warning"""
        m = make_mic()
        rec = watch_alerts(m)
        for q in (35, 20, 5):
            m.update_signal_quality(q)
        self.assertEqual(rec.severities(), [W])

    def test_pin_va_tin_hieu_la_hai_vung_doc_lap(self):
        """Pin thấp rồi tín hiệu thấp: mỗi chỉ số cảnh báo riêng (2 Warning)"""
        m = make_mic()
        rec = watch_alerts(m)
        m.update_battery_level(20)
        m.update_signal_quality(30)
        self.assertEqual(rec.severities(), [W, W])

    def test_phuc_hoi_roi_tut_lai_phat_lai(self):
        """Tín hiệu yếu -> tốt -> yếu: cảnh báo lại"""
        m = make_mic()
        rec = watch_alerts(m)
        m.update_signal_quality(10)
        m.update_signal_quality(90)
        m.update_signal_quality(10)
        self.assertEqual(rec.severities(), [W, W])


# ======================================================================
#  6. EVENT ARGS, ENUM, NGOẠI LỆ
# ======================================================================
class TestDataClasses(unittest.TestCase):
    def test_enum_day_du_gia_tri(self):
        """Enum có đủ thành viên theo đề"""
        self.assertEqual({s.name for s in DeviceStatus},
                         {"AVAILABLE", "BORROWED", "UNDER_MAINTENANCE"})
        self.assertEqual({s.name for s in AlertSeverity},
                         {"INFORMATION", "WARNING", "CRITICAL"})

    def test_ngoai_le_luu_thong_tin(self):
        """InvalidDeviceReadingException có DeviceId, InvalidValue và là Exception"""
        ex = InvalidDeviceReadingException("MIC01", 150)
        self.assertIsInstance(ex, Exception)
        self.assertEqual(ex.device_id, "MIC01")
        self.assertEqual(ex.invalid_value, 150)
        self.assertIn("150", str(ex))
        self.assertIn("MIC01", str(ex))

    def test_alert_event_args_chi_doc(self):
        """DeviceAlertEventArgs chỉ đọc (đề dùng { get; })"""
        e = make_alert(W)
        with self.assertRaises(AttributeError):
            e.message = "bị sửa"

    def test_status_event_args_chi_doc(self):
        """DeviceStatusChangedEventArgs chỉ đọc"""
        e = DeviceStatusChangedEventArgs(
            "AC01", DeviceStatus.AVAILABLE, DeviceStatus.BORROWED, datetime.now())
        with self.assertRaises(AttributeError):
            e.new_status = DeviceStatus.AVAILABLE


# ======================================================================
#  7. SUBSCRIBER
# ======================================================================
class TestConsoleNotificationService(QuietTestCase):
    def test_in_dung_dinh_dang(self):
        """In đúng mẫu: [Severity] DeviceId: Message"""
        ConsoleNotificationService().handle_alert(
            None, make_alert(W, "PRJ01", "Pin thấp"))
        self.assertEqual(self.printed.strip(), "[Warning] PRJ01: Pin thấp")

    def test_in_ca_critical(self):
        """In được cả mức Critical"""
        ConsoleNotificationService().handle_alert(
            None, make_alert(C, "AC01", "Mất phản hồi"))
        self.assertEqual(self.printed.strip(), "[Critical] AC01: Mất phản hồi")

    def test_khong_con_ham_xu_ly_trang_thai(self):
        """Đề chỉ giao HandleAlert cho ConsoleNotificationService"""
        self.assertFalse(hasattr(ConsoleNotificationService(), "handle_status_changed"))


class TestDeviceAuditLogger(QuietTestCase):
    def setUp(self):
        super().setUp()
        self.dev = make_ac()
        self.audit = DeviceAuditLogger()
        self.dev.add_status_changed_handler(self.audit.handle_status_changed)

    def test_ban_dau_rong(self):
        """Logger mới chưa có bản ghi"""
        self.assertEqual(len(self.audit.entries), 0)

    def test_ghi_log_khi_doi_trang_thai(self):
        """Mỗi lần đổi trạng thái ghi 1 dòng chứa id, trạng thái cũ và mới"""
        self.dev.change_status(DeviceStatus.BORROWED)
        self.assertEqual(len(self.audit.entries), 1)
        line = self.audit.entries[0]
        for part in ("AC01", "Available", "Borrowed"):
            self.assertIn(part, line)

    def test_khong_ghi_log_khi_trung_trang_thai(self):
        """Đổi sang cùng trạng thái -> không có log"""
        self.dev.change_status(DeviceStatus.AVAILABLE)
        self.assertEqual(len(self.audit.entries), 0)

    def test_entries_chi_doc(self):
        """Bên ngoài không sửa được entries (không append/clear được)"""
        self.dev.change_status(DeviceStatus.BORROWED)
        with self.assertRaises(AttributeError):
            self.audit.entries.append("giả mạo")
        with self.assertRaises(AttributeError):
            self.audit.entries.clear()
        self.assertEqual(len(self.audit.entries), 1)

    def test_khong_in_ra_man_hinh(self):
        """Logger chỉ ghi vào danh sách, không print"""
        self.dev.change_status(DeviceStatus.BORROWED)
        self.assertEqual(self.printed, "")


class TestMaintenanceService(QuietTestCase):
    def test_chi_tao_yeu_cau_voi_critical(self):
        """Warning và Information không tạo yêu cầu bảo trì"""
        svc = MaintenanceService()
        svc.handle_critical_alert(None, make_alert(W))
        svc.handle_critical_alert(None, make_alert(AlertSeverity.INFORMATION))
        self.assertEqual(len(svc.requests), 0)

    def test_critical_tao_dung_noi_dung(self):
        """Critical tạo 1 yêu cầu đúng mẫu đề"""
        svc = MaintenanceService()
        svc.handle_critical_alert(None, make_alert(C, "AC01", "Mất phản hồi"))
        self.assertEqual(list(svc.requests),
                         ["Maintenance request for AC01: Mất phản hồi"])

    def test_requests_chi_doc(self):
        """Bên ngoài không sửa được requests"""
        svc = MaintenanceService()
        svc.handle_critical_alert(None, make_alert(C))
        with self.assertRaises(AttributeError):
            svc.requests.append("giả mạo")
        self.assertEqual(len(svc.requests), 1)


# ======================================================================
#  8. DELEGATE: FilteredAlertSubscriber
# ======================================================================
class TestFilteredAlertSubscriber(QuietTestCase):
    def test_loc_dung_thi_goi_action(self):
        """Filter trả True -> action được gọi với đúng event"""
        got = []
        sub = FilteredAlertSubscriber(lambda a: True, got.append)
        e = make_alert(C)
        sub.handle_alert(None, e)
        self.assertEqual(got, [e])

    def test_loc_sai_thi_khong_goi_action(self):
        """Filter trả False -> action không được gọi"""
        got = []
        sub = FilteredAlertSubscriber(lambda a: False, got.append)
        sub.handle_alert(None, make_alert(C))
        self.assertEqual(got, [])

    def test_vi_du_chi_critical(self):
        """Filter 'chỉ Critical' như ví dụ trong đề"""
        got = []
        sub = FilteredAlertSubscriber(lambda a: a.severity == C,
                                      lambda a: got.append(a.severity))
        sub.handle_alert(None, make_alert(W))
        sub.handle_alert(None, make_alert(C))
        self.assertEqual(got, [C])

    def test_dung_nhu_subscriber_cua_event_that(self):
        """Gắn vào AlertRaised của thiết bị: chỉ nhận Critical"""
        got = []
        sub = FilteredAlertSubscriber(lambda a: a.severity == C,
                                      lambda a: got.append(a.message))
        p = make_projector(90)
        p.add_alert_raised_handler(sub.handle_alert)
        p.update_battery_level(15)   # Warning -> bị lọc
        p.update_battery_level(0)    # Critical -> nhận
        self.assertEqual(len(got), 1)


# ======================================================================
#  9. COORDINATOR
# ======================================================================
class TestCoordinator(QuietTestCase):
    def setUp(self):
        super().setUp()
        self.proj = make_projector(90)
        self.ac = make_ac()
        self.mic = make_mic()
        self.notif = ConsoleNotificationService()
        self.audit = DeviceAuditLogger()
        self.maint = MaintenanceService()
        self.coord = DeviceMonitoringCoordinator(
            [self.proj, self.ac, self.mic], self.notif, self.audit, self.maint)

    def test_chua_subscribe_thi_khong_co_gi_xay_ra(self):
        """Chưa Subscribe: đổi trạng thái / cảnh báo không ai xử lý"""
        self.proj.change_status(DeviceStatus.BORROWED)
        self.ac.update_response_state(False)
        self.assertEqual(len(self.audit.entries), 0)
        self.assertEqual(len(self.maint.requests), 0)
        self.assertEqual(self.printed, "")

    def test_subscribe_noi_day_du_cac_handler(self):
        """Subscribe: audit ghi log, console in cảnh báo, bảo trì nhận Critical"""
        self.coord.subscribe()
        self.proj.change_status(DeviceStatus.BORROWED)
        self.ac.update_response_state(False)
        self.assertEqual(len(self.audit.entries), 1)
        self.assertEqual(len(self.maint.requests), 1)
        self.assertIn("[Critical] AC01", self.printed)

    def test_subscribe_ap_dung_cho_moi_thiet_bi(self):
        """Cả 3 thiết bị đều được theo dõi"""
        self.coord.subscribe()
        self.proj.change_status(DeviceStatus.BORROWED)
        self.ac.change_status(DeviceStatus.BORROWED)
        self.mic.change_status(DeviceStatus.BORROWED)
        self.assertEqual(len(self.audit.entries), 3)

    def test_warning_khong_tao_yeu_cau_bao_tri(self):
        """Đầu-cuối: pin 15% chỉ hiện cảnh báo, chưa tạo bảo trì; pin 0% mới tạo"""
        self.coord.subscribe()
        self.proj.update_battery_level(15)
        self.assertIn("[Warning] PRJ01", self.printed)
        self.assertEqual(len(self.maint.requests), 0)
        self.proj.update_battery_level(0)
        self.assertEqual(len(self.maint.requests), 1)

    def test_subscribe_hai_lan_khong_dang_ky_trung(self):
        """Subscribe 2 lần: một cảnh báo chỉ xử lý 1 lần"""
        self.coord.subscribe()
        self.coord.subscribe()
        self.ac.update_response_state(False)
        self.assertEqual(len(self.maint.requests), 1)
        self.assertEqual(self.printed.count("[Critical] AC01"), 1)
        self.proj.change_status(DeviceStatus.BORROWED)
        self.assertEqual(len(self.audit.entries), 1)

    def test_unsubscribe_huy_het_cac_handler(self):
        """Unsubscribe: sau đó không còn log, không in, không tạo bảo trì"""
        self.coord.subscribe()
        self.coord.unsubscribe()
        before = self.printed
        self.proj.change_status(DeviceStatus.BORROWED)
        self.ac.update_response_state(False)
        self.proj.update_battery_level(0)
        self.assertEqual(len(self.audit.entries), 0)
        self.assertEqual(len(self.maint.requests), 0)
        self.assertEqual(self.printed, before)

    def test_unsubscribe_khi_chua_subscribe_khong_loi(self):
        """Gọi Unsubscribe khi chưa Subscribe không gây lỗi"""
        self.coord.unsubscribe()

    def test_dispose_goi_unsubscribe(self):
        """Dispose() có tác dụng như Unsubscribe()"""
        self.coord.subscribe()
        self.coord.dispose()
        self.proj.change_status(DeviceStatus.BORROWED)
        self.assertEqual(len(self.audit.entries), 0)

    def test_subscribe_lai_sau_unsubscribe(self):
        """Subscribe -> Unsubscribe -> Subscribe: hoạt động lại, không nhân đôi"""
        self.coord.subscribe()
        self.coord.unsubscribe()
        self.coord.subscribe()
        self.proj.change_status(DeviceStatus.BORROWED)
        self.assertEqual(len(self.audit.entries), 1)

    def test_unsubscribe_khong_anh_huong_handler_cua_ben_khac(self):
        """Unsubscribe chỉ gỡ đăng ký do Coordinator tạo, handler khác vẫn chạy"""
        other = Recorder()
        self.proj.add_alert_raised_handler(other)
        self.coord.subscribe()
        self.coord.unsubscribe()
        self.proj.update_battery_level(0)
        self.assertEqual(other.severities(), [C])

    def test_doi_cung_trang_thai_qua_coordinator_khong_ghi_log(self):
        """Đầu-cuối: Available -> Available không sinh log"""
        self.coord.subscribe()
        self.proj.change_status(DeviceStatus.AVAILABLE)
        self.assertEqual(len(self.audit.entries), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)