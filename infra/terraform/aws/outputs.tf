output "public_ip" {
  description = "Public IP of the instance."
  value       = aws_instance.kurz.public_ip
}

output "ssh_tunnel" {
  description = "Opens a tunnel to the Kubernetes API; then use the copied kubeconfig against 127.0.0.1:6443."
  value       = "ssh -N -L 6443:127.0.0.1:6443 ubuntu@${aws_instance.kurz.public_ip}"
}

output "fetch_kubeconfig" {
  description = "Copies the k3s kubeconfig to your machine."
  value       = "scp ubuntu@${aws_instance.kurz.public_ip}:/etc/rancher/k3s/k3s.yaml ./kubeconfig-kurz.yaml"
}
