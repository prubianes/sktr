class OrderRepository:
    def find(self, order_id: str) -> dict[str, str] | None:
        return {"id": order_id, "status": "created"}
