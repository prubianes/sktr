package com.sample.services;

import com.sample.repositories.OrderRepository;

public class OrderService {
    private final OrderRepository repository = new OrderRepository();

    public String getOrder(String id) {
        return repository.find(id);
    }
}
