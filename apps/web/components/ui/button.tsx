import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-[background-color,color,opacity,transform] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-ink hover:-translate-y-px hover:opacity-90",
        secondary: "bg-elev text-ink border border-line hover:bg-bg",
        ghost: "text-ink hover:bg-black/5 dark:hover:bg-white/10",
        danger: "bg-ink text-bg hover:opacity-90",
      },
      size: {
        md: "h-11 px-4",
        sm: "h-9 px-3 text-[13px]",
        icon: "h-10 w-10",
        lg: "px-6 py-3 text-base font-semibold",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  },
);
Button.displayName = "Button";
