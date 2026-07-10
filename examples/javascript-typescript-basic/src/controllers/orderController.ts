import { OrderRepository } from "../repositories/orderRepository";

export class OrderController {
  constructor(private readonly repository = new OrderRepository()) {}

  getOrder(id: string) {
    return this.repository.find(id);
  }
}
