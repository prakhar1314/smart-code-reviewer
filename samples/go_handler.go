package main

import (
	"encoding/json"
	"net/http"
)

type Order struct {
	ID     string  `json:"id"`
	Amount float64 `json:"amount"`
}

var orders = []Order{}

func handler(w http.ResponseWriter, r *http.Request) {
	if r.Method == "POST" {
		var o Order
		json.NewDecoder(r.Body).Decode(&o)
		orders = append(orders, o)
		w.WriteHeader(201)
	} else if r.Method == "GET" {
		json.NewEncoder(w).Encode(orders)
	}
}

func main() {
	http.HandleFunc("/orders", handler)
	http.ListenAndServe(":8080", nil)
}
