from abc import ABC, abstractmethod

class BrokerBase(ABC):
    @abstractmethod
    def buy(self, symbol: str, qty: float, limit_price: float | None = None, stop_price: float | None = None, stop_limit_price: float | None = None, extended_hours: bool = False):
        pass

    @abstractmethod
    def sell(self, symbol: str, qty: float, limit_price: float | None = None, stop_price: float | None = None, stop_limit_price: float | None = None, extended_hours: bool = False):
        pass

    @abstractmethod
    def get_position(self, symbol: str):
        pass

    @abstractmethod
    def get_all_positions(self):
        pass

    @abstractmethod
    def get_orders(self, status: str = "all", limit: int = 20):
        pass

    @abstractmethod
    def get_account_equity(self) -> float:
        pass

    @abstractmethod
    def cancel_all_orders(self):
        pass
