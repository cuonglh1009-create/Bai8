#/****************/
# Họ tên: Lê Hùng Cường
# MSSV: 202418859
#/****************/

import sys
from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime
from typing import Callable, List, Optional, Tuple

# Tự động cấu hình mã hóa UTF-8 cho console terminal trên Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")



# 1. ENUMS 

class DeviceStatus(Enum):
    AVAILABLE = "Available"
    BORROWED = "Borrowed"
    UNDER_MAINTENANCE = "UnderMaintenance"


class AlertSeverity(Enum):
    INFORMATION = "Information"
    WARNING = "Warning"
    CRITICAL = "Critical"



# 2. EVENT ARGS 
class DeviceStatusChangedEventArgs:
    """Lớp dữ liệu cho sự kiện thay đổi trạng thái thiết bị"""
    def __init__(self, device_id: str, old_status: DeviceStatus,
                 new_status: DeviceStatus, changed_at: datetime):
        self._device_id = device_id
        self._old_status = old_status
        self._new_status = new_status
        self._changed_at = changed_at

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def old_status(self) -> DeviceStatus:
        return self._old_status

    @property
    def new_status(self) -> DeviceStatus:
        return self._new_status

    @property
    def changed_at(self) -> datetime:
        return self._changed_at


class DeviceAlertEventArgs:
    """Lớp dữ liệu cho sự kiện cảnh báo thiết bị"""
    def __init__(self, device_id: str, message: str,
                 severity: AlertSeverity, occurred_at: datetime):
        self._device_id = device_id
        self._message = message
        self._severity = severity
        self._occurred_at = occurred_at

    @property
    def device_id(self) -> str:
        return self._device_id

    @property
    def message(self) -> str:
        return self._message

    @property
    def severity(self) -> AlertSeverity:
        return self._severity

    @property
    def occurred_at(self) -> datetime:
        return self._occurred_at


# 3. NGOẠI LỆ 

class InvalidDeviceReadingException(Exception):
    """Phát sinh khi chỉ số pin hoặc tín hiệu nằm ngoài khoảng 0-100"""
    def __init__(self, device_id: str, invalid_value: int):
        self.device_id = device_id
        self.invalid_value = invalid_value
        super().__init__(f"Giá trị không hợp lệ {invalid_value} trên thiết bị {device_id} (Phải từ 0 đến 100)")


# 4. LỚP TRỪU TƯỢNG TEACHING DEVICE 

class TeachingDevice(ABC):
    def __init__(self, device_id: str, name: str):
        if not device_id or not name:
            raise ValueError("Id và Name không được rỗng")
        self._id = device_id
        self._name = name
        self._status = DeviceStatus.AVAILABLE

        # Danh sách subscriber mô phỏng event trong C# (+= và -=)
        self._status_changed_handlers: List[Callable] = []
        self._alert_raised_handlers: List[Callable] = []

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> DeviceStatus:
        return self._status

    # Đăng ký / hủy đăng ký event StatusChanged
    def add_status_changed_handler(self, handler: Callable):
        if handler not in self._status_changed_handlers:
            self._status_changed_handlers.append(handler)

    def remove_status_changed_handler(self, handler: Callable):
        if handler in self._status_changed_handlers:
            self._status_changed_handlers.remove(handler)

    # Đăng ký / hủy đăng ký event AlertRaised
    def add_alert_raised_handler(self, handler: Callable):
        if handler not in self._alert_raised_handlers:
            self._alert_raised_handlers.append(handler)

    def remove_alert_raised_handler(self, handler: Callable):
        if handler in self._alert_raised_handlers:
            self._alert_raised_handlers.remove(handler)

    # Đổi trạng thái thiết bị: Không phát sinh event nếu trùng trạng thái cũ
    def change_status(self, new_status: DeviceStatus):
        if new_status == self._status:
            return
        old_status = self._status
        self._status = new_status
        args = DeviceStatusChangedEventArgs(
            self.id, old_status, new_status, datetime.now()
        )
        self._on_status_changed(args)

    # Protected virtual methods phát sinh event
    def _on_status_changed(self, e: DeviceStatusChangedEventArgs):
        for handler in list(self._status_changed_handlers):
            handler(self, e)

    def _raise_alert(self, message: str, severity: AlertSeverity):
        args = DeviceAlertEventArgs(
            self.id, message, severity, datetime.now()
        )
        self._on_alert_raised(args)

    def _on_alert_raised(self, e: DeviceAlertEventArgs):
        for handler in list(self._alert_raised_handlers):
            handler(self, e)

    def __str__(self):
        return f"[{self.id}] {self.name} | Trạng thái: {self.status.value}"



# 5. CÁC LỚP THIẾT BỊ CON 
class ProjectorRemote(TeachingDevice):
    """Điều khiển máy chiếu"""
    def __init__(self, device_id: str, name: str, battery_level: int):
        super().__init__(device_id, name)
        if not 0 <= battery_level <= 100:
            raise InvalidDeviceReadingException(device_id, battery_level)
        self._battery_level = battery_level

    @property
    def battery_level(self) -> int:
        return self._battery_level

    @staticmethod
    def _zone(level: int) -> int:
        """
        Phân vùng cảnh báo pin:
        - 2: Critical (Pin = 0%)
        - 1: Warning (0% < Pin < 20%)
        - 0: Safe (Pin >= 20%)
        """
        if level == 0:
            return 2
        if level < 20:
            return 1
        return 0

    def update_battery_level(self, new_level: int):
        if not 0 <= new_level <= 100:
            raise InvalidDeviceReadingException(self.id, new_level)

        old_zone = self._zone(self._battery_level)
        self._battery_level = new_level
        new_zone = self._zone(new_level)

        # Chỉ phát sinh cảnh báo khi thay đổi vùng (không lặp lại trong cùng vùng an toàn/warning/critical)
        if new_zone != old_zone:
            if new_zone == 2:
                self._raise_alert("Pin hết (0%)", AlertSeverity.CRITICAL)
            elif new_zone == 1:
                self._raise_alert(f"Pin thấp còn {new_level}%", AlertSeverity.WARNING)

    # Alias tiện ích
    def update_battery(self, new_level: int):
        self.update_battery_level(new_level)

    def __str__(self):
        return f"{super().__str__()} | Pin: {self.battery_level}%"


class AirConditionerRemote(TeachingDevice):
    """Điều khiển điều hòa"""
    def __init__(self, device_id: str, name: str, assigned_room: str):
        super().__init__(device_id, name)
        self._assigned_room = assigned_room
        self._is_responsive = True

    @property
    def assigned_room(self) -> str:
        return self._assigned_room

    @property
    def is_responsive(self) -> bool:
        return self._is_responsive

    def update_response_state(self, is_responsive: bool):
        was_responsive = self._is_responsive
        self._is_responsive = is_responsive
        # Khi chuyển từ phản hồi sang không phản hồi -> phát sinh cảnh báo Critical
        # Không phát sinh lặp lại nếu trạng thái vẫn là không phản hồi
        if was_responsive and not is_responsive:
            self._raise_alert(
                f"Điều khiển điều hòa tại phòng {self.assigned_room} không phản hồi",
                AlertSeverity.CRITICAL
            )

    def __str__(self):
        resp = "Bình thường" if self.is_responsive else "Không phản hồi"
        return f"{super().__str__()} | Phòng: {self.assigned_room} | Tín hiệu: {resp}"


class WirelessMicrophone(TeachingDevice):
    """Micro không dây"""
    def __init__(self, device_id: str, name: str,
                 battery_level: int, signal_quality: int):
        super().__init__(device_id, name)
        if not 0 <= battery_level <= 100:
            raise InvalidDeviceReadingException(device_id, battery_level)
        if not 0 <= signal_quality <= 100:
            raise InvalidDeviceReadingException(device_id, signal_quality)
        self._battery_level = battery_level
        self._signal_quality = signal_quality

    @property
    def battery_level(self) -> int:
        return self._battery_level

    @property
    def signal_quality(self) -> int:
        return self._signal_quality

    @staticmethod
    def _battery_zone(level: int) -> int:
        """
        Phân vùng cảnh báo pin Micro:
        - 2: Critical (Pin = 0%)
        - 1: Warning (0% < Pin < 30%)
        - 0: Safe (Pin >= 30%)
        """
        if level == 0:
            return 2
        if level < 30:
            return 1
        return 0

    @staticmethod
    def _signal_zone(quality: int) -> int:
        """
        Phân vùng cảnh báo chất lượng tín hiệu Micro:
        - 2: Critical (Tín hiệu = 0%)
        - 1: Warning (0% < Tín hiệu < 40%)
        - 0: Safe (Tín hiệu >= 40%)
        """
        if quality == 0:
            return 2
        if quality < 40:
            return 1
        return 0

    def update_battery_level(self, new_level: int):
        if not 0 <= new_level <= 100:
            raise InvalidDeviceReadingException(self.id, new_level)
        old_zone = self._battery_zone(self._battery_level)
        self._battery_level = new_level
        new_zone = self._battery_zone(new_level)
        if new_zone != old_zone:
            if new_zone == 2:
                self._raise_alert("Pin micro đã cạn (0%)", AlertSeverity.CRITICAL)
            elif new_zone == 1:
                self._raise_alert(f"Pin micro yếu còn {new_level}%", AlertSeverity.WARNING)

    def update_signal_quality(self, new_quality: int):
        if not 0 <= new_quality <= 100:
            raise InvalidDeviceReadingException(self.id, new_quality)
        old_zone = self._signal_zone(self._signal_quality)
        self._signal_quality = new_quality
        new_zone = self._signal_zone(new_quality)
        if new_zone != old_zone:
            if new_zone == 2:
                self._raise_alert("Micro mất hoàn toàn tín hiệu (0%)", AlertSeverity.CRITICAL)
            elif new_zone == 1:
                self._raise_alert(f"Chất lượng tín hiệu micro yếu còn {new_quality}%", AlertSeverity.WARNING)

    # Alias tiện ích
    def update_signal(self, new_quality: int):
        self.update_signal_quality(new_quality)

    def update_battery(self, new_level: int):
        self.update_battery_level(new_level)

    def __str__(self):
        return f"{super().__str__()} | Pin: {self.battery_level}% | Tín hiệu: {self.signal_quality}%"



# 6. CÁC SUBSCRIBER 
class ConsoleNotificationService:
    """Hiển thị cảnh báo ra Console"""
    def handle_alert(self, sender, e: DeviceAlertEventArgs):
        print(f"[{e.severity.value}] {e.device_id}: {e.message}")


class DeviceAuditLogger:
    """Ghi lại lịch sử thay đổi trạng thái"""
    def __init__(self):
        self._entries: List[str] = []

    @property
    def entries(self) -> Tuple[str, ...]:
        # Trả về tuple chỉ đọc để bên ngoài không tự append() hay clear() được
        return tuple(self._entries)

    # Alias logs để tương thích code cũ
    @property
    def logs(self) -> Tuple[str, ...]:
        return self.entries

    def handle_status_changed(self, sender, e: DeviceStatusChangedEventArgs):
        # Format theo chuẩn C# trong đề: $"{e.ChangedAt}: {e.DeviceId}, {e.OldStatus} -> {e.NewStatus}"
        entry = (f"{e.changed_at.strftime('%Y-%m-%d %H:%M:%S')}: {e.device_id}, "
                 f"{e.old_status.value} -> {e.new_status.value}")
        self._entries.append(entry)


class MaintenanceService:
    """Tạo yêu cầu bảo trì khi có cảnh báo Critical"""
    def __init__(self):
        self._requests: List[str] = []

    @property
    def requests(self) -> Tuple[str, ...]:
        # Trả về tuple chỉ đọc để bên ngoài không sửa được
        return tuple(self._requests)

    def handle_critical_alert(self, sender, e: DeviceAlertEventArgs):
        if e.severity != AlertSeverity.CRITICAL:
            return
        req = f"Maintenance request for {e.device_id}: {e.message}"
        self._requests.append(req)
        print(f"[MAINTENANCE] Đã tạo phiếu bảo trì cho {e.device_id}: {e.message}")


# 7. DELEGATE VÀ FILTERED SUBSCRIBER (Mục 8 trong đề bài)

AlertFilter = Callable[[DeviceAlertEventArgs], bool]

class FilteredAlertSubscriber:
    """Subscriber có bộ lọc điều kiện (Delegate callback)"""
    def __init__(self, filter_func: AlertFilter,
                 action: Callable[[DeviceAlertEventArgs], None]):
        self._filter = filter_func
        self._action = action

    def handle_alert(self, sender, e: DeviceAlertEventArgs):
        if self._filter(e):
            self._action(e)


# 8. LỚP ĐIỀU PHỐI ĐĂNG KÝ 
class DeviceMonitoringCoordinator:
    """Điều phối đăng ký và hủy đăng ký các event handler"""
    def __init__(self, devices: List[TeachingDevice],
                 notification: ConsoleNotificationService,
                 audit: DeviceAuditLogger,
                 maintenance: MaintenanceService):
        self._devices = devices
        self._notification = notification
        self._audit = audit
        self._maintenance = maintenance
        self._subscribed = False

    def subscribe(self):
        # Tránh đăng ký trùng cùng handler nhiều lần
        if self._subscribed:
            print("Hệ thống đã được đăng ký trước đó rồi.")
            return
        for d in self._devices:
            d.add_alert_raised_handler(self._notification.handle_alert)
            d.add_alert_raised_handler(self._maintenance.handle_critical_alert)
            d.add_status_changed_handler(self._audit.handle_status_changed)
        self._subscribed = True
        print("-> Đã đăng ký tất cả handler thành công.")

    def unsubscribe(self):
        if not self._subscribed:
            print("Hệ thống hiện chưa đăng ký handler.")
            return
        for d in self._devices:
            d.remove_alert_raised_handler(self._notification.handle_alert)
            d.remove_alert_raised_handler(self._maintenance.handle_critical_alert)
            d.remove_status_changed_handler(self._audit.handle_status_changed)
        self._subscribed = False
        print("-> Đã hủy đăng ký tất cả handler.")

    def dispose(self):
        # Dispose() gọi Unsubscribe() theo yêu cầu mục 9
        self.unsubscribe()



# 9. GIAO DIỆN CONSOLE MENU & TEST

def print_menu():
    print("      HỆ THỐNG QUẢN LÝ THIẾT BỊ GIẢNG DẠY")
    print("1. Xem danh sách thiết bị")
    print("2. Đổi trạng thái thiết bị (Available/Borrowed/UnderMaintenance)")
    print("3. Cập nhật pin Projector (0-100%)")
    print("4. Cập nhật kết nối Điều hòa (Bình thường / Mất kết nối)")
    print("5. Cập nhật pin Micro không dây (0-100%)")
    print("6. Cập nhật tín hiệu Micro không dây (0-100%)")
    print("7. Xem lịch sử thay đổi (Audit Logger)")
    print("8. Xem danh sách yêu cầu bảo trì (Maintenance)")
    print("9. Quản lý Subscribe / Unsubscribe Coordinator")
    print("0. Thoát")



def main():
    # 1. Khởi tạo danh sách thiết bị
    proj = ProjectorRemote("PRJ01", "Điều khiển Epson", 90)
    ac = AirConditionerRemote("AC01", "ĐK Điều hòa Daikin", "Phòng 302")
    mic = WirelessMicrophone("MIC01", "Micro Shure", 70, 85)

    devices: List[TeachingDevice] = [proj, ac, mic]

    # 2. Khởi tạo các Subscribers
    notification = ConsoleNotificationService()
    audit = DeviceAuditLogger()
    maintenance = MaintenanceService()

    # 3. Khởi tạo Coordinator và đăng ký
    coordinator = DeviceMonitoringCoordinator(
        devices, notification, audit, maintenance
    )
    coordinator.subscribe()

    # 4. Thử nghiệm FilteredAlertSubscriber (Lọc riêng các cảnh báo Critical)
    critical_filter = FilteredAlertSubscriber(
        filter_func=lambda e: e.severity == AlertSeverity.CRITICAL,
        action=lambda e: print(f"*** [BỘ LỌC CHỈ CRITICAL] {e.device_id}: {e.message} ***")
    )
    for d in devices:
        d.add_alert_raised_handler(critical_filter.handle_alert)

    # Vòng lặp menu
    while True:
        print_menu()
        choice = input("Mời bạn chọn (0-9): ").strip()

        try:
            if choice == "1":
                print("\n--- DANH SÁCH THIẾT BỊ ---")
                for d in devices:
                    print(" *", d)

            elif choice == "2":
                did = input("Nhập mã thiết bị (PRJ01/AC01/MIC01): ").strip().upper()
                device = next((d for d in devices if d.id == did), None)
                if not device:
                    print("-> Không tìm thấy thiết bị!")
                    continue
                print("Chọn trạng thái: 1.Available  2.Borrowed  3.UnderMaintenance")
                s = input("Lựa chọn: ").strip()
                mapping = {
                    "1": DeviceStatus.AVAILABLE,
                    "2": DeviceStatus.BORROWED,
                    "3": DeviceStatus.UNDER_MAINTENANCE
                }
                if s in mapping:
                    device.change_status(mapping[s])
                    print(f"-> Đã đổi trạng thái {device.id} thành {mapping[s].value}")
                else:
                    print("-> Lựa chọn trạng thái không hợp lệ.")

            elif choice == "3":
                level = int(input("Nhập mức pin mới cho Projector (0-100): "))
                proj.update_battery_level(level)
                print(f"-> Đã cập nhật pin Projector thành {level}%")

            elif choice == "4":
                print("1. Đang kết nối bình thường  |  2. Mất kết nối (Không phản hồi)")
                sub_c = input("Chọn trạng thái phản hồi: ").strip()
                if sub_c == "1":
                    ac.update_response_state(True)
                    print("-> Đã chuyển trạng thái AC: Phản hồi bình thường")
                elif sub_c == "2":
                    ac.update_response_state(False)
                    print("-> Đã chuyển trạng thái AC: Mất phản hồi")
                else:
                    print("-> Lựa chọn không hợp lệ.")

            elif choice == "5":
                level = int(input("Nhập mức pin mới cho Micro (0-100): "))
                mic.update_battery_level(level)
                print(f"-> Đã cập nhật pin Micro thành {level}%")

            elif choice == "6":
                q = int(input("Nhập chất lượng tín hiệu mới cho Micro (0-100): "))
                mic.update_signal_quality(q)
                print(f"-> Đã cập nhật tín hiệu Micro thành {q}%")

            elif choice == "7":
                print("\n--- NHẬT KÝ THAY ĐỔI (DEVICE AUDIT LOG) ---")
                if not audit.entries:
                    print("  (Chưa có bản ghi nào)")
                else:
                    for log in audit.entries:
                        print(" ", log)

            elif choice == "8":
                print("\n--- DANH SÁCH YÊU CẦU BẢO TRÌ (MAINTENANCE REQUESTS) ---")
                if not maintenance.requests:
                    print("  (Chưa có yêu cầu nào)")
                else:
                    for r in maintenance.requests:
                        print(" ", r)

            elif choice == "9":
                print("1. Subscribe tất cả   |   2. Unsubscribe tất cả")
                sub = input("Chọn: ").strip()
                if sub == "1":
                    coordinator.subscribe()
                elif sub == "2":
                    coordinator.unsubscribe()
                else:
                    print("-> Lựa chọn không hợp lệ.")

            elif choice == "0":
                coordinator.dispose()
                print("Hệ thống đã dọn dẹp và thoát chương trình. Tạm biệt!")
                break
            else:
                print("-> Lựa chọn không hợp lệ, vui lòng chọn lại!")

        except InvalidDeviceReadingException as e:
            print(f"\n[LỖI ĐỌC THIẾT BỊ] {e}")
        except ValueError as e:
            print(f"\n[LỖI DỮ LIỆU NHẬP] {e}")
        except Exception as e:
            print(f"\n[LỖI NGOẠI LỆ] {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
