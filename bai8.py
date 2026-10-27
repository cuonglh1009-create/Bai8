#/****************/
# Họ tên: Lê Hùng Cường
# MSSV: 202418859
#/****************/

from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime
from typing import Callable, List, Optional


#  ENUM
class DeviceStatus(Enum):
    AVAILABLE = "Available"
    BORROWED = "Borrowed"
    UNDER_MAINTENANCE = "UnderMaintenance"


class AlertSeverity(Enum):
    INFORMATION = "Information"
    WARNING = "Warning"
    CRITICAL = "Critical"


#  EVENT ARGS
class DeviceStatusChangedEventArgs:
    def __init__(self, device_id: str, old_status: DeviceStatus,
                 new_status: DeviceStatus, changed_at: datetime):
        self.device_id = device_id
        self.old_status = old_status
        self.new_status = new_status
        self.changed_at = changed_at


class DeviceAlertEventArgs:
    def __init__(self, device_id: str, message: str,
                 severity: AlertSeverity, occurred_at: datetime):
        self.device_id = device_id
        self.message = message
        self.severity = severity
        self.occurred_at = occurred_at


#  NGOẠI LỆ
class InvalidDeviceReadingException(Exception):
    def __init__(self, device_id: str, invalid_value: int):
        self.device_id = device_id
        self.invalid_value = invalid_value
        super().__init__(f"Giá trị không hợp lệ {invalid_value} trên thiết bị {device_id}")


#  TEACHING DEVICE (PUBLISHER)
class TeachingDevice(ABC):
    def __init__(self, device_id: str, name: str):
        if not device_id or not name:
            raise ValueError("Id và Name không được rỗng")
        self._id = device_id
        self._name = name
        self._status = DeviceStatus.AVAILABLE

        # Danh sách subscriber (mô phỏng event)
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

    #  Đăng ký / hủy đăng ký
    def add_status_changed_handler(self, handler: Callable):
        if handler not in self._status_changed_handlers:
            self._status_changed_handlers.append(handler)

    def remove_status_changed_handler(self, handler: Callable):
        if handler in self._status_changed_handlers:
            self._status_changed_handlers.remove(handler)

    def add_alert_raised_handler(self, handler: Callable):
        if handler not in self._alert_raised_handlers:
            self._alert_raised_handlers.append(handler)

    def remove_alert_raised_handler(self, handler: Callable):
        if handler in self._alert_raised_handlers:
            self._alert_raised_handlers.remove(handler)

    def change_status(self, new_status: DeviceStatus):
        if new_status == self._status:
            return
        old = self._status
        self._status = new_status
        args = DeviceStatusChangedEventArgs(
            self.id, old, new_status, datetime.now()
        )
        self._on_status_changed(args)

    def _on_status_changed(self, e: DeviceStatusChangedEventArgs):
        for handler in self._status_changed_handlers:
            handler(self, e)

    def _raise_alert(self, message: str, severity: AlertSeverity):
        args = DeviceAlertEventArgs(
            self.id, message, severity, datetime.now()
        )
        self._on_alert_raised(args)

    def _on_alert_raised(self, e: DeviceAlertEventArgs):
        for handler in self._alert_raised_handlers:
            handler(self, e)

    def __str__(self):
        return f"[{self.id}] {self.name} | {self.status.value}"


#  CÁC LỚP DẪN XUẤT
class ProjectorRemote(TeachingDevice):
    def __init__(self, device_id: str, name: str, battery_level: int):
        super().__init__(device_id, name)
        if not 0 <= battery_level <= 100:
            raise InvalidDeviceReadingException(device_id, battery_level)
        self._battery_level = battery_level

    @property
    def battery_level(self) -> int:
        return self._battery_level

    def update_battery(self, new_level: int):
        if not 0 <= new_level <= 100:
            raise InvalidDeviceReadingException(self.id, new_level)
        self._battery_level = new_level
        if new_level < 20:
            self.rasie_alert(
                f"Pin thấp còn {new_level}%",
                AlertSeverity.WARNING if new_level >= 10 else AlertSeverity.CRITICAL
            )


class AirConditionerRemote(TeachingDevice):
    def __init__(self, device_id: str, name: str):
        super().__init__(device_id, name)


class WirelessMicrophone(TeachingDevice):
    def __init__(self, device_id: str, name: str,
                 battery_level: int, signal_quality: int):
        super().__init__(device_id, name)
        if not 0 <= battery_level <= 100:
            raise InvalidDeviceReadingException(device_id, battery_level)
        if not 0 <= signal_quality <= 100:
            raise InvalidDeviceReadingException(device_id, signal_quality)
        self._battery_level = battery_level
        self._signal_quality = signal_quality

    def update_signal(self, new_quality: int):
        if not 0 <= new_quality <= 100:
            raise InvalidDeviceReadingException(self.id, new_quality)
        self._signal_quality = new_quality
        if new_quality < 40:
            self.rasie_alert(
                f"Tín hiệu yếu còn {new_quality}%",
                AlertSeverity.WARNING
            )


#  SUBSCRIBER
class ConsoleNotificationService:
    def handle_alert(self, sender, e: DeviceAlertEventArgs):
        print(f"[{e.severity.value}] {e.device_id}: {e.message}")


class DeviceAuditLogger:
    def __init__(self):
        self.logs: List[str] = []
    def handle_status_changed(self, sender, e: DeviceStatusChangedEventArgs):
        entry = (f"{e.changed_at.isoformat()} | {e.device_id} | "
                 f"{e.old_status.value} → {e.new_status.value}")
        self.logs.append(entry)
  


class MaintenanceService:
    def __init__(self):
        self.requests: List[str] = []

    def handle_critical_alert(self, sender, e: DeviceAlertEventArgs):
        if e.severity != AlertSeverity.CRITICAL:
            return
        self._requests.append(
            f"Maintenance request for {e.device_id}: {e.message}"
        )
        print(f"[MAINT] Tạo yêu cầu bảo trì: {e.device_id}")


# FILTERED SUBSCRIBER
# Mô phỏng delegate AlertFilter
AlertFilter = Callable[[DeviceAlertEventArgs], bool]

class FilteredAlertSubscriber:
    def __init__(self, filter_func: AlertFilter,
                 action: Callable[[DeviceAlertEventArgs], None]):
        self._filter = filter_func
        self._action = action

    def handle_alert(self, sender, e: DeviceAlertEventArgs):
        if self._filter(e):
            self._action(e)


#  COORDINATOR
class DeviceMonitoringCoordinator:
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
        if self._subscribed:
            return
        for d in self._devices:
            d.add_alert_raised_handler(self._notification.handle_alert)
            d.add_alert_raised_handler(self._maintenance.handle_critical_alert)
            d.add_status_changed_handler(self._audit.handle_status_changed)
        self._subscribed = True
        print("Đã đăng ký tất cả handler.")

    def unsubscribe(self):
        if not self._subscribed:
            return
        for d in self._devices:
            d.remove_alert_raised_handler(self._notification.handle_alert)
            d.remove_alert_raised_handler(self._maintenance.handle_critical_alert)
            d.remove_status_changed_handler(self._audit.handle_status_changed)
        self._subscribed = False
        print("Đã hủy đăng ký tất cả handler.")

    def dispose(self):
        self.unsubscribe()


#  MENU
def print_menu():
    print(" Chọn chức năng:")
    print("1. Xem danh sách thiết bị")
    print("2. Đổi trạng thái thiết bị")
    print("3. Cập nhật pin Projector (có thể phát Alert)")
    print("4. Cập nhật tín hiệu Micro (có thể phát Alert)")
    print("5. Xem log Audit")
    print("6. Xem yêu cầu bảo trì")
    print("7. Đăng ký / Hủy đăng ký Coordinator")
    print("0. Thoát")


def main():
    # Tạo thiết bị
    proj = ProjectorRemote("PRJ01", "Điều khiển Epson", 90)
    ac = AirConditionerRemote("AC01", "ĐK Điều hòa Daikin")
    mic = WirelessMicrophone("MIC01", "Micro Shure", 70, 85)

    devices = [proj, ac, mic]

    notification = ConsoleNotificationService()
    audit = DeviceAuditLogger()
    maintenance = MaintenanceService()

    coordinator = DeviceMonitoringCoordinator(
        devices, notification, audit, maintenance
    )
    coordinator.subscribe()

    # Filtered subscriber chỉ Critical
    critical_filter = FilteredAlertSubscriber(
        filter_func=lambda e: e.severity == AlertSeverity.CRITICAL,
        action=lambda e: print(f"*** CRITICAL ONLY *** {e.device_id}: {e.message}")
    )
    for d in devices:
        d.add_alert_raised_handler(critical_filter.handle_alert)


    while True:
        print_menu()
        choice = input("Chọn: ").strip()

        try:
            if choice == "1":
                for d in devices:
                    print(" ", d)

            elif choice == "2":
                did = input("Mã thiết bị: ").strip()
                device = next((d for d in devices if d.id == did), None)
                if not device:
                    print("Không tìm thấy.")
                    continue
                print("1.Available  2.Borrowed  3.UnderMaintenance")
                s = input("Trạng thái mới: ").strip()
                mapping = {
                    "1": DeviceStatus.AVAILABLE,
                    "2": DeviceStatus.BORROWED,
                    "3": DeviceStatus.UNDER_MAINTENANCE
                }
                if s in mapping:
                    device.change_status(mapping[s])
                else:
                    print("Lựa chọn sai.")

            elif choice == "3":
                level = int(input("Mức pin mới (0-100): "))
                proj.update_battery(level)

            elif choice == "4":
                q = int(input("Chất lượng tín hiệu mới (0-100): "))
                mic.update_signal(q)

            elif choice == "5":
                print("--- Audit log ---")
                for log in audit.logs:
                    print(" ", log)
                if not audit.logs:
                    print("  (trống)")

            elif choice == "6":
                print("--- Maintenance requests ---")
                for r in maintenance.requests:
                    print(" ", r)
                if not maintenance.requests:
                    print("  (trống)")

            elif choice == "7":
                print("1. Subscribe lại   2. Unsubscribe")
                sub = input("Chọn: ").strip()
                if sub == "1":
                    coordinator.subscribe()
                elif sub == "2":
                    coordinator.unsubscribe()

            elif choice == "0":
                coordinator.dispose()
                print("Tạm biệt!")
                break
            else:
                print("Lựa chọn không hợp lệ.")

        except InvalidDeviceReadingException as e:
            print(f"[LỖI ĐỌC] {e}")
        except ValueError as e:
            print(f"[LỖI DỮ LIỆU] {e}")
        except Exception as e:
            print(f"[LỖI HỆ THỐNG] {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()
