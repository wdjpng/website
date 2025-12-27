import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
from matplotlib.ticker import LogFormatterMathtext


def compute_optimal_lambda_and_variance(mu: float, sigma: float, n_points: int = 800):
    """
    Compute the optimal lambda and minimal variance of Schulman's KL estimator
    when q ~ N(0,1) and p ~ N(mu, sigma^2).
    """
    # Integration grid covering most of p's mass
    x_min = mu - 6 * sigma
    x_max = mu + 6 * sigma
    x = np.linspace(x_min, x_max, n_points)
    dx = x[1] - x[0]

    # Densities
    p = np.exp(-0.5 * ((x - mu) / sigma) ** 2) / (sigma * np.sqrt(2 * np.pi))
    q = np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)

    # Avoid zeros
    p = np.maximum(p, 1e-300)
    q = np.maximum(q, 1e-300)

    r = q / p
    log_r = np.log(r)
    r_minus_1 = r - 1

    # Expectations under p
    E = lambda f: np.sum(f * p) * dx

    E_log_r = E(log_r)
    E_log_r_sq = E(log_r**2)
    Var_log_r = E_log_r_sq - E_log_r**2

    E_r = E(r)
    E_r_sq = E(r**2)
    Var_r = E_r_sq - E_r**2

    E_log_r_times_r = E(log_r * r)
    Cov_log_r_r = E_log_r_times_r - E_log_r * E_r

    E_log_r_times_r_minus_1 = E(log_r * r_minus_1)
    E_r_minus_1_sq = E(r_minus_1**2)

    if E_r_minus_1_sq < 1e-15:
        lambda_opt = 1.0
    else:
        lambda_opt = E_log_r_times_r_minus_1 / E_r_minus_1_sq

    min_variance = (
        Var_log_r
        + lambda_opt**2 * Var_r
        - 2 * lambda_opt * Cov_log_r_r
    )
    min_variance = max(min_variance, 1e-12)  # clamp for log scale stability

    return lambda_opt, min_variance


def main():
    # Grid
    n_grid = 320
    sigma_vals = np.linspace(0.55, 2.05, n_grid)
    mu_vals = np.linspace(0.0, 2.0, n_grid)

    opt_lambda = np.zeros((n_grid, n_grid))
    min_var = np.zeros((n_grid, n_grid))

    for i, mu in enumerate(mu_vals):
        for j, sigma in enumerate(sigma_vals):
            lam, var = compute_optimal_lambda_and_variance(mu, sigma)
            opt_lambda[i, j] = lam
            min_var[i, j] = var

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Left: optimal lambda
    im1 = ax1.imshow(
        opt_lambda,
        origin="lower",
        aspect="auto",
        extent=[sigma_vals[0], sigma_vals[-1], mu_vals[0], mu_vals[-1]],
        cmap="magma",
        vmin=0.4,
        vmax=2.2,
    )
    ax1.set_xlabel(r"Standard deviation $\sigma$ of p")
    ax1.set_ylabel(r"Mean $\mu$ of p")
    cbar1 = fig.colorbar(im1, ax=ax1)
    cbar1.set_label(r"Optimal $\lambda$")

    # Right: minimal variance
    im2 = ax2.imshow(
        min_var,
        origin="lower",
        aspect="auto",
        extent=[sigma_vals[0], sigma_vals[-1], mu_vals[0], mu_vals[-1]],
        cmap="magma",
        norm=LogNorm(vmin=1e-10, vmax=1e0),
    )
    ax2.set_xlabel(r"Standard deviation $\sigma$ of p")
    ax2.set_ylabel(r"Mean $\mu$ of p")
    formatter = LogFormatterMathtext()
    cbar2 = fig.colorbar(im2, ax=ax2, format=formatter)
    cbar2.set_label("Minimal Variance")

    plt.tight_layout()
    plt.savefig("/home/wdjpng/repos/website/assets/img/kl_div.png", dpi=150, bbox_inches="tight")


if __name__ == "__main__":
    main()
import numpy as np
import matplotlib.pyplot as plt
from scipy import integrate

def compute_optimal_lambda_and_variance(mu, sigma, n_points=1000):
    """
    Compute optimal lambda and minimal variance for KL estimator.
    q is N(0,1), p is N(mu, sigma^2)
    """
    # Integration range - need to cover where p has significant mass
    x_min = mu - 6*sigma
    x_max = mu + 6*sigma
    x = np.linspace(x_min, x_max, n_points)
    dx = x[1] - x[0]
    
    # p(x) = N(mu, sigma^2)
    p = np.exp(-0.5 * ((x - mu) / sigma)**2) / (sigma * np.sqrt(2 * np.pi))
    
    # q(x) = N(0, 1)
    q = np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)
    
    # Avoid division by zero
    p = np.maximum(p, 1e-300)
    q = np.maximum(q, 1e-300)
    
    # r(x) = q(x) / p(x)
    r = q / p
    
    # Compute expectations under p
    # E_p[f] = integral of f(x) * p(x) dx
    
    log_r = np.log(r)
    r_minus_1 = r - 1
    
    # E_p[log(r) * (r-1)]
    E_log_r_times_r_minus_1 = np.sum(log_r * r_minus_1 * p) * dx
    
    # E_p[(r-1)^2]
    E_r_minus_1_sq = np.sum(r_minus_1**2 * p) * dx
    
    # Optimal lambda
    if E_r_minus_1_sq < 1e-15:
        lambda_opt = 1.0
    else:
        lambda_opt = E_log_r_times_r_minus_1 / E_r_minus_1_sq
    
    # Compute variance at optimal lambda
    # Var[L] = Var[log r] + lambda^2 * Var[r] - 2*lambda*Cov[log r, r]
    
    E_log_r = np.sum(log_r * p) * dx
    E_log_r_sq = np.sum(log_r**2 * p) * dx
    Var_log_r = E_log_r_sq - E_log_r**2
    
    E_r = np.sum(r * p) * dx  # Should be ~1
    E_r_sq = np.sum(r**2 * p) * dx
    Var_r = E_r_sq - E_r**2
    
    # Cov[log r, r] = E[log r * r] - E[log r] * E[r]
    E_log_r_times_r = np.sum(log_r * r * p) * dx
    Cov_log_r_r = E_log_r_times_r - E_log_r * E_r
    
    # Variance at optimal lambda
    # Note: we use -log r in estimator, so Var[-log r] = Var[log r]
    min_variance = Var_log_r + lambda_opt**2 * Var_r - 2 * lambda_opt * Cov_log_r_r
    
    return lambda_opt, max(min_variance, 1e-15)

# Create grid
n_grid = 200
sigma_range = np.linspace(0.5, 2.0, n_grid)
mu_range = np.linspace(0.0, 2.0, n_grid)

optimal_lambda = np.zeros((n_grid, n_grid))
minimal_variance = np.zeros((n_grid, n_grid))

print("Computing...")
for i, mu in enumerate(mu_range):
    if i % 20 == 0:
        print(f"Progress: {i}/{n_grid}")
    for j, sigma in enumerate(sigma_range):
        lam, var = compute_optimal_lambda_and_variance(mu, sigma)
        optimal_lambda[i, j] = lam
        minimal_variance[i, j] = var

print("Plotting...")

# Create figure
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))

# Left plot: Optimal lambda
im1 = ax1.imshow(optimal_lambda, origin='lower', aspect='auto',
                  extent=[sigma_range[0], sigma_range[-1], mu_range[0], mu_range[-1]],
                  cmap='inferno', vmin=0.5, vmax=2.2)
ax1.set_xlabel(r'Standard deviation $\sigma$ of p', fontsize=12)
ax1.set_ylabel(r'Mean $\mu$ of p', fontsize=12)
cbar1 = plt.colorbar(im1, ax=ax1)
cbar1.set_label(r'Optimal $\lambda$', fontsize=12)

# Right plot: Minimal variance (log scale)
im2 = ax2.imshow(minimal_variance, origin='lower', aspect='auto',
                  extent=[sigma_range[0], sigma_range[-1], mu_range[0], mu_range[-1]],
                  cmap='inferno', norm=plt.matplotlib.colors.LogNorm(vmin=1e-10, vmax=1e0))
ax2.set_xlabel(r'Standard deviation $\sigma$ of p', fontsize=12)
ax2.set_ylabel(r'Mean $\mu$ of p', fontsize=12)
cbar2 = plt.colorbar(im2, ax=ax2)
cbar2.set_label('Minimal Variance', fontsize=12)

plt.tight_layout()
plt.savefig('/home/wdjpng/repos/website/assets/img/kl_div.png', dpi=150, bbox_inches='tight')
plt.savefig('/home/wdjpng/repos/website/assets/img/kl_div_new.png', dpi=150, bbox_inches='tight')
print("Saved to /home/wdjpng/repos/website/assets/img/kl_div.png")
plt.show()

