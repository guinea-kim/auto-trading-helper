from abc import ABC, abstractmethod

class MarketStrategy(ABC):
    """Abstract base class for different market strategies"""

    @abstractmethod
    def get_manager(self, user_id):
        """Get or create manager for the specific market"""
        pass

    @abstractmethod
    def get_db_handler(self):
        """Get database handler for the specific market"""
        pass

    @abstractmethod
    def extract_order_id(self, manager, hash_value, order):
        """Extract order ID from the order response"""
        pass
