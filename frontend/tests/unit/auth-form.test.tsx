import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthForm, validateAuth } from "@/components/auth/auth-form";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { ApiError } from "@/lib/api";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe("validateAuth", () => {
  it("requires a 10+ character password only when registering", () => {
    expect(validateAuth("register", { name: "A", email: "a@b.co", password: "short" }).password).toBeDefined();
    expect(validateAuth("login", { name: "", email: "a@b.co", password: "short" })).toEqual({});
  });
});

describe("AuthForm", () => {
  it("shows validation errors and does not submit invalid input", async () => {
    const onSubmit = vi.fn();
    render(<AuthForm mode="register" onSubmit={onSubmit} />);
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(screen.getByText("Enter your name")).toBeInTheDocument();
    expect(screen.getByText("Enter a valid email address")).toBeInTheDocument();
    expect(screen.getByLabelText(/Email/)).toHaveAttribute("aria-invalid", "true");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits trimmed values and shows the server error", async () => {
    const onSubmit = vi.fn().mockRejectedValue(new ApiError(401, "invalid_credentials", "Email or password is incorrect"));
    render(<AuthForm mode="login" onSubmit={onSubmit} />);
    await userEvent.type(screen.getByLabelText(/Email/), "  qa@example.com ");
    await userEvent.type(screen.getByLabelText(/Password/), "secret-password");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(onSubmit).toHaveBeenCalledWith({ name: "", email: "qa@example.com", password: "secret-password" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect");
  });
});

describe("states", () => {
  it("renders an empty state with its action", () => {
    render(<EmptyState title="No documents yet" description="Upload one" action={<button>Upload</button>} />);
    expect(screen.getByText("No documents yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
  });

  it("renders an error state with retry", async () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError(500, "internal_error", "Boom")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Boom");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
