from repositories.order_repository import OrderRepository


def get_order(order_id: str) -> dict[str, str] | None:
    return OrderRepository().find(order_id)
