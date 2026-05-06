'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { fetchVariantCapabilities } from '@/lib/api';
import type { VariantCapability } from '@/lib/types';
import { Skeleton } from '@/components/ui/skeleton';
import { Check, X } from 'lucide-react';

export function CapabilityMatrix() {
  const [capabilities, setCapabilities] = useState<VariantCapability[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchVariantCapabilities().then(d => { setCapabilities(d); setLoading(false); });
  }, []);

  if (loading) {
    return <Card><CardContent className="p-6"><Skeleton className="h-96 w-full" /></CardContent></Card>;
  }

  const categories = [...new Set(capabilities.map(c => c.category))];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Capability Matrix</CardTitle>
        <CardDescription>Feature availability across variant tiers</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left font-medium text-muted-foreground pb-3 pr-4 min-w-[200px]">Feature</th>
                <th className="text-center font-medium text-muted-foreground pb-3 px-4">
                  <span className="text-emerald-600 dark:text-emerald-400">Starter</span>
                  <br /><span className="text-[10px] font-normal">(mini_parwa)</span>
                </th>
                <th className="text-center font-medium text-muted-foreground pb-3 px-4">
                  <span className="text-amber-600 dark:text-amber-400">Growth</span>
                  <br /><span className="text-[10px] font-normal">(parwa)</span>
                </th>
                <th className="text-center font-medium text-muted-foreground pb-3 px-4">
                  <span className="text-red-600 dark:text-red-400">High</span>
                  <br /><span className="text-[10px] font-normal">(parwa_high)</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {categories.map(category => (
                <>
                  <tr key={`cat-${category}`} className="bg-muted/30">
                    <td colSpan={4} className="py-2 px-4 font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                      {category}
                    </td>
                  </tr>
                  {capabilities.filter(c => c.category === category).map(cap => (
                    <tr key={cap.featureId} className="border-b border-border/30 hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 pr-4 pl-4">{cap.featureName}</td>
                      <td className="py-2.5 text-center px-4">
                        {cap.mini_parwa ? (
                          <Check className="h-4 w-4 text-emerald-600 dark:text-emerald-400 mx-auto" />
                        ) : (
                          <X className="h-4 w-4 text-muted-foreground/30 mx-auto" />
                        )}
                      </td>
                      <td className="py-2.5 text-center px-4">
                        {cap.parwa ? (
                          <Check className="h-4 w-4 text-amber-600 dark:text-amber-400 mx-auto" />
                        ) : (
                          <X className="h-4 w-4 text-muted-foreground/30 mx-auto" />
                        )}
                      </td>
                      <td className="py-2.5 text-center px-4">
                        {cap.parwa_high ? (
                          <Check className="h-4 w-4 text-red-600 dark:text-red-400 mx-auto" />
                        ) : (
                          <X className="h-4 w-4 text-muted-foreground/30 mx-auto" />
                        )}
                      </td>
                    </tr>
                  ))}
                </>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
