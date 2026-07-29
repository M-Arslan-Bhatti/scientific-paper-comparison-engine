resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}-${var.environment}"
  retention_in_days = 30
}

resource "aws_ecs_cluster" "app" {
  name = "${var.project_name}-${var.environment}"
}

resource "aws_lb" "app" {
  name               = "${var.project_name}-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids
}

resource "aws_lb_target_group" "app" {
  name        = "${var.project_name}-${var.environment}"
  port        = 8501
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    path                = "/_stcore/health"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 5
    timeout             = 10
    interval            = 30
    matcher             = "200"
  }
}

resource "aws_lb_listener" "app" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = "${var.project_name}-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "app"
      # Placeholder tag until the CD workflow pushes the first real image.
      # The ECS service won't reach a healthy state until then.
      image     = "${aws_ecr_repository.app.repository_url}:latest"
      essential = true
      portMappings = [
        { containerPort = 8501, protocol = "tcp" }
      ]
      environment = [
        { name = "AWS_DEFAULT_REGION", value = var.aws_region },
        { name = "BEDROCK_LLM_MODEL", value = var.bedrock_llm_model },
        { name = "BEDROCK_EMBED_MODEL", value = var.bedrock_embed_model },
        { name = "PINECONE_INDEX_NAME", value = var.pinecone_index_name },
        { name = "PINECONE_ENVIRONMENT", value = var.pinecone_environment },
      ]
      secrets = [
        {
          name      = "PINECONE_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.app_env.arn}:PINECONE_API_KEY::"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "app"
        }
      }
    }
  ])

  tags = { Project = var.project_name, Environment = var.environment }
}

resource "aws_ecs_service" "app" {
  name            = "${var.project_name}-${var.environment}"
  cluster         = aws_ecs_cluster.app.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ecs_service.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = 8501
  }

  # The CD workflow deploys new images by registering a new task definition
  # revision and updating the service — Terraform shouldn't fight that by
  # reverting to whatever image tag is in this config.
  lifecycle {
    ignore_changes = [task_definition]
  }

  depends_on = [aws_lb_listener.app]
}
