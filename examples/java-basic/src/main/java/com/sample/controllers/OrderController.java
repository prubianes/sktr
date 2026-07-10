package com.sample.controllers;

import com.sample.repositories.OrderRepository;

public class OrderController {
    private final OrderRepository repository = new OrderRepository();

    public String getOrder(String id) {
        return repository.find(id);
    }
}
