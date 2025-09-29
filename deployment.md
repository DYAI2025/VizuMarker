# Production Deployment Configuration

## Environment Variables

Create a `.env` file with the following variables:

```bash
SECRET_KEY=your-super-secret-key-change-in-production
LD35_MODEL_PATH=/models/ld35_model
STORAGE_PATH=/app/storage
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
ALLOWED_ORIGINS=http://yourdomain.com,https://yourdomain.com
```

## Deployment with Docker Compose

1. Build and start the services:
```bash
docker-compose up -d
```

2. Scale workers as needed:
```bash
docker-compose up -d --scale celery-worker=3
```

## Kubernetes Deployment (Optional)

For production Kubernetes deployments, you would need:

- `k8s/ld35-service-deployment.yaml`
- `k8s/ld35-service-service.yaml` 
- `k8s/redis-deployment.yaml`
- `k8s/redis-service.yaml`
- `k8s/celery-worker-deployment.yaml`

## Monitoring and Logging

- API logs are available through Docker: `docker-compose logs ld35-service`
- Celery worker logs: `docker-compose logs celery-worker`
- Prometheus/Grafana can be added for metrics

## Scaling Considerations

- API service can be scaled based on request volume
- Celery workers should be scaled based on queue length and processing time
- Redis should be monitored for memory usage
- Storage volumes need to be managed for large document processing

## Security Considerations

- Use HTTPS in production
- Rotate SECRET_KEY regularly
- Restrict ALLOWED_ORIGINS to trusted domains only
- Implement rate limiting for API endpoints
- Secure access to Redis and storage volumes

## Health Checks

- API health endpoint: `GET /health`
- Celery monitoring: `celery -A ld35_service.workers.annotation_tasks.celery_app inspect active`