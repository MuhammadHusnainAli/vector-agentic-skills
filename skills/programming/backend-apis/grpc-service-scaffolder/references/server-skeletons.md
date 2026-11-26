# Server Skeletons

## Go (grpc-go)

```go
func main() {
    lis, _ := net.Listen("tcp", ":8080")
    srv := grpc.NewServer(
        grpc.ChainUnaryInterceptor(recovery.UnaryServerInterceptor(), logging.UnaryServerInterceptor(logger), authUnary),
        grpc.ChainStreamInterceptor(recovery.StreamServerInterceptor(), authStream),
        grpc.StatsHandler(otelgrpc.NewServerHandler()),                 // tracing + metrics
        grpc.KeepaliveParams(keepalive.ServerParameters{MaxConnectionAge: 30 * time.Minute, MaxConnectionAgeGrace: 30 * time.Second}),
        grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{MinTime: 10 * time.Second, PermitWithoutStream: true}),
        grpc.MaxRecvMsgSize(4 << 20),
        grpc.MaxConcurrentStreams(1000),
    )
    ordersv1.RegisterOrderServiceServer(srv, &orderServer{svc: domain.NewOrders(db)})
    hs := health.NewServer()
    healthpb.RegisterHealthServer(srv, hs)
    hs.SetServingStatus("acme.orders.v1.OrderService", healthpb.HealthCheckResponse_SERVING)

    go func() { _ = srv.Serve(lis) }()
    sig := make(chan os.Signal, 1); signal.Notify(sig, syscall.SIGTERM, os.Interrupt); <-sig
    hs.Shutdown()                                                       // report NOT_SERVING first
    done := make(chan struct{}); go func() { srv.GracefulStop(); close(done) }()
    select { case <-done: case <-time.After(25 * time.Second): srv.Stop() }
}

func (s *orderServer) GetOrder(ctx context.Context, req *ordersv1.GetOrderRequest) (*ordersv1.GetOrderResponse, error) {
    o, err := s.svc.Get(ctx, req.GetId())                               // ctx carries the deadline
    switch {
    case errors.Is(err, domain.ErrNotFound): return nil, status.Error(codes.NotFound, "order not found")
    case err != nil: return nil, status.Error(codes.Internal, "internal error")   // details logged, not returned
    }
    return &ordersv1.GetOrderResponse{Order: toProto(o)}, nil
}
```
`MaxConnectionAge` makes clients reconnect periodically so new backends get traffic.

## Python (grpcio asyncio)

```python
async def serve():
    server = grpc.aio.server(interceptors=[AuthInterceptor(), LoggingInterceptor()],
                             options=[("grpc.max_receive_message_length", 4 << 20),
                                      ("grpc.max_connection_age_ms", 30 * 60 * 1000)])
    orders_pb2_grpc.add_OrderServiceServicer_to_server(OrderServicer(), server)
    health_servicer = health.aio.HealthServicer()
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    server.add_insecure_port("[::]:8080")
    await server.start()
    loop = asyncio.get_running_loop(); stop = asyncio.Event()
    loop.add_signal_handler(signal.SIGTERM, stop.set)
    await stop.wait()
    await health_servicer.enter_graceful_shutdown()
    await server.stop(grace=25)
```
Check `context.time_remaining()` and pass it to downstream calls as their timeout.

## Node.js / TypeScript (Connect)

```ts
import { ConnectRouter } from "@connectrpc/connect";
import { fastify } from "fastify";
import { fastifyConnectPlugin } from "@connectrpc/connect-fastify";

const routes = (router: ConnectRouter) => router.service(OrderService, {
  async getOrder(req, ctx) {                       // ctx.signal aborts on deadline/cancel
    const order = await orders.get(req.id, { signal: ctx.signal });
    if (!order) throw new ConnectError("order not found", Code.NotFound);
    return { order };
  },
});
const app = fastify({ http2: true });
await app.register(fastifyConnectPlugin, { routes, interceptors: [authInterceptor, loggingInterceptor] });
await app.listen({ host: "0.0.0.0", port: 8080 });
```
Connect serves gRPC, gRPC-Web and the Connect protocol (browser-friendly) from one handler. `@grpc/grpc-js` is the
alternative for plain gRPC.

## Java / Kotlin

- grpc-java with `NettyServerBuilder`: `.intercept(...)`, `.maxInboundMessageSize`, `.maxConnectionAge`,
  `HealthStatusManager`, `server.shutdown().awaitTermination(25, SECONDS)` then `shutdownNow()`.
- Spring: `grpc-spring` / Spring gRPC starters register services as beans and wire interceptors and health.

## .NET (Grpc.AspNetCore)

```csharp
builder.Services.AddGrpc(o => { o.Interceptors.Add<ErrorInterceptor>(); o.MaxReceiveMessageSize = 4 * 1024 * 1024; });
builder.Services.AddGrpcHealthChecks().AddCheck("db", () => HealthCheckResult.Healthy());
app.MapGrpcService<OrderService>();
app.MapGrpcHealthChecksService();
```
Graceful shutdown via `HostOptions.ShutdownTimeout`; `ServerCallContext.CancellationToken` for cancellation.

## Rust (tonic)

```rust
let (health_reporter, health_service) = tonic_health::server::health_reporter();
health_reporter.set_serving::<OrderServiceServer<MyOrders>>().await;
Server::builder()
    .timeout(Duration::from_secs(10))
    .layer(tower::ServiceBuilder::new().layer(TraceLayer::new_for_grpc()))
    .add_service(health_service)
    .add_service(OrderServiceServer::with_interceptor(MyOrders::new(db), check_auth))
    .serve_with_shutdown(addr, shutdown_signal())
    .await?;
```

## Testing

- Go: `bufconn` in-process listener; Python: `grpc.aio` server on an ephemeral port; Java: `InProcessServerBuilder`;
  .NET: `WebApplicationFactory` + `GrpcChannel` with the test handler; Node: Connect's router transport.
- Test status codes, deadlines (client sets 50 ms; server respects it), auth failures and streaming termination.
