"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Bot, Ticket, Plug, Target } from "lucide-react";

const cards = [
  {
    title: "Active Variants",
    value: "1",
    description: "PARWA • 2,000 tickets",
    icon: Bot,
    color: "text-emerald-500",
    bg: "bg-emerald-100 dark:bg-emerald-900/30",
  },
  {
    title: "Tickets Today",
    value: "0",
    description: "0 resolved by AI",
    icon: Ticket,
    color: "text-blue-500",
    bg: "bg-blue-100 dark:bg-blue-900/30",
  },
  {
    title: "Integrations",
    value: "0",
    description: "0 connected",
    icon: Plug,
    color: "text-purple-500",
    bg: "bg-purple-100 dark:bg-purple-900/30",
  },
  {
    title: "AI Accuracy",
    value: "—",
    description: "Not enough data yet",
    icon: Target,
    color: "text-amber-500",
    bg: "bg-amber-100 dark:bg-amber-900/30",
  },
];

export function OverviewCards() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <Card key={card.title} className="hover:shadow-md transition-shadow">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-medium text-muted-foreground">{card.title}</p>
              <div className={`h-8 w-8 rounded-lg ${card.bg} flex items-center justify-center`}>
                <card.icon className={`h-4 w-4 ${card.color}`} />
              </div>
            </div>
            <p className="text-2xl font-bold">{card.value}</p>
            <p className="text-xs text-muted-foreground mt-1">{card.description}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
