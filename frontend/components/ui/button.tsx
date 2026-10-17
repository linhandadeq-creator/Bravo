import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { playSound } from "@/lib/sound";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "press inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-2xl text-[13px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-accent text-accent-foreground lg-edge-strong hover:brightness-110",
        outline:
          "lg-2 lg-edge text-foreground hover:lg-3",
        secondary:
          "lg-1 lg-edge text-foreground hover:lg-2",
        ghost:
          "text-muted-foreground hover:lg-1 hover:text-foreground",
        link: "text-accent underline-offset-4 hover:underline",
        destructive:
          "bg-destructive text-destructive-foreground lg-edge-strong hover:brightness-110",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-xl px-3 text-[12px]",
        lg: "h-11 rounded-2xl px-6",
        icon: "h-9 w-9 rounded-full",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, onClick, disabled, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        disabled={disabled}
        onClick={(event) => {
          if (!disabled) playSound("click");
          onClick?.(event);
        }}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
