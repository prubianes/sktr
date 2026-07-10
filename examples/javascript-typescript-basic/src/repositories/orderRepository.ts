export type Order = { id: string; status: string };

export class OrderRepository {
  find(id: string): Order {
    return { id, status: "created" };
  }
}
