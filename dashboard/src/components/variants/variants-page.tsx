'use client';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAppStore } from '@/lib/store';
import { InstanceList } from './instance-list';
import { CapabilityMatrix } from './capability-matrix';
import { WorkloadChart } from './workload-chart';
import { EntitlementSummary } from './entitlement-summary';
import { CostBudget } from './cost-budget';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter, DialogClose } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useState } from 'react';
import { Plus, Cpu, LayoutGrid, PieChart, CreditCard, List } from 'lucide-react';
import { createVariantInstance } from '@/lib/api';
import type { VariantType, ChannelType } from '@/lib/types';
import { useToast } from '@/hooks/use-toast';

function CreateInstanceDialog() {
  const [name, setName] = useState('');
  const [type, setType] = useState<VariantType>('mini_parwa');
  const [channel, setChannel] = useState<ChannelType>('chat');
  const [capacity, setCapacity] = useState(500);
  const [creating, setCreating] = useState(false);
  const { toast } = useToast();

  const handleCreate = async () => {
    setCreating(true);
    try {
      await createVariantInstance({ name, type, channel, capacity });
      toast({ title: 'Instance created', description: `${name} has been created successfully.` });
    } catch {
      toast({ title: 'Error', description: 'Failed to create instance.', variant: 'destructive' });
    }
    setCreating(false);
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button className="bg-emerald-600 hover:bg-emerald-700 text-white">
          <Plus className="h-4 w-4 mr-2" /> New Instance
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Variant Instance</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div><Label>Instance Name</Label><Input value={name} onChange={e => setName(e.target.value)} placeholder="My Variant" className="mt-1" /></div>
          <div><Label>Variant Type</Label>
            <Select value={type} onValueChange={v => setType(v as VariantType)}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="mini_parwa">Starter (mini_parwa) - 10 nodes</SelectItem>
                <SelectItem value="parwa">Growth (parwa) - 22 nodes</SelectItem>
                <SelectItem value="parwa_high">High (parwa_high) - 27 nodes</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div><Label>Channel</Label>
            <Select value={channel} onValueChange={v => setChannel(v as ChannelType)}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="chat">Chat</SelectItem>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="sms">SMS</SelectItem>
                <SelectItem value="voice">Voice</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div><Label>Capacity</Label><Input type="number" value={capacity} onChange={e => setCapacity(Number(e.target.value))} className="mt-1" /></div>
        </div>
        <DialogFooter>
          <DialogClose asChild><Button variant="outline">Cancel</Button></DialogClose>
          <Button onClick={handleCreate} disabled={creating || !name} className="bg-emerald-600 hover:bg-emerald-700 text-white">
            {creating ? 'Creating...' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function VariantsPage() {
  const { variantTab, setVariantTab } = useAppStore();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Tabs value={variantTab} onValueChange={setVariantTab}>
          <TabsList>
            <TabsTrigger value="instances"><List className="h-3 w-3 mr-1" /> Instances</TabsTrigger>
            <TabsTrigger value="capabilities"><LayoutGrid className="h-3 w-3 mr-1" /> Capabilities</TabsTrigger>
            <TabsTrigger value="workload"><PieChart className="h-3 w-3 mr-1" /> Workload</TabsTrigger>
            <TabsTrigger value="entitlements"><Cpu className="h-3 w-3 mr-1" /> Entitlements</TabsTrigger>
            <TabsTrigger value="budget"><CreditCard className="h-3 w-3 mr-1" /> Budget</TabsTrigger>
          </TabsList>
        </Tabs>
        <CreateInstanceDialog />
      </div>
      <TabsContent value="instances" className="mt-0"><InstanceList /></TabsContent>
      <TabsContent value="capabilities" className="mt-0"><CapabilityMatrix /></TabsContent>
      <TabsContent value="workload" className="mt-0"><WorkloadChart /></TabsContent>
      <TabsContent value="entitlements" className="mt-0"><EntitlementSummary /></TabsContent>
      <TabsContent value="budget" className="mt-0"><CostBudget /></TabsContent>
    </div>
  );
}
