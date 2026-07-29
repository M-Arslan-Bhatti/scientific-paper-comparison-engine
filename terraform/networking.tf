# Uses the account's default VPC/subnets to keep this FYP-scale deployment
# simple — no NAT gateway cost, tasks get a public IP directly. For a real
# multi-tenant production system, replace this with a dedicated VPC with
# private subnets + NAT.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb"
  description = "Allow inbound HTTP to the ALB"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Project = var.project_name }
}

resource "aws_security_group" "ecs_service" {
  name        = "${var.project_name}-ecs-service"
  description = "Allow inbound from ALB to the Streamlit container"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Streamlit from ALB"
    from_port       = 8501
    to_port         = 8501
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Project = var.project_name }
}
