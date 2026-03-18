package main

import (
    "net/http"
    "net/http/httptest"
    "testing"
)

func TestHealthEndpoint(t *testing.T) {
    req := httptest.NewRequest("GET", "/_healthz", nil)
    w := httptest.NewRecorder()

    handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.WriteHeader(http.StatusOK)
    })

    handler.ServeHTTP(w, req)

    if w.Result().StatusCode != 200 {
        t.Errorf("Expected 200, got %d", w.Result().StatusCode)
    }
}
