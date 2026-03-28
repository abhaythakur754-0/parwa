'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { CreditCard, Download, Calendar, Users, FileText, Receipt } from 'lucide-react';

/**
 * Enterprise Billing Page
 * 
 * Displays contract details, invoices, and billing history
 * for enterprise customers.
 */

const contractDetails = {
  contractId: 'ENT-2024-001',
  companyName: 'Acme Corporation',
  plan: 'Enterprise',
  seatsIncluded: 50,
  seatsUsed: 45,
  billingCycle: 'Annual',
  startDate: '2024-01-15',
  endDate: '2025-01-14',
  monthlyValue: '$4,950.00',
  status: 'active'
};

const invoices = [
  {
    id: 'INV-2024-003',
    date: '2024-01-15',
    amount: '$59,400.00',
    status: 'paid',
    period: 'Jan 2024 - Jan 2025'
  },
  {
    id: 'INV-2023-003',
    date: '2023-01-15',
    amount: '$54,000.00',
    status: 'paid',
    period: 'Jan 2023 - Jan 2024'
  },
  {
    id: 'INV-2022-003',
    date: '2022-01-15',
    amount: '$48,000.00',
    status: 'paid',
    period: 'Jan 2022 - Jan 2023'
  }
];

const usageBreakdown = [
  { category: 'API Calls', included: '100,000', used: '78,432', unit: 'calls' },
  { category: 'AI Responses', included: '50,000', used: '42,150', unit: 'responses' },
  { category: 'Storage', included: '100', used: '67', unit: 'GB' },
  { category: 'Team Members', included: '50', used: '45', unit: 'seats' }
];

export default function EnterpriseBillingPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Enterprise Billing</h1>
          <p className="text-muted-foreground">
            View contract details, invoices, and usage
          </p>
        </div>
        <Badge variant="secondary" className="text-sm bg-green-100 text-green-800">
          Active Contract
        </Badge>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Contract Overview */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <FileText className="h-5 w-5" />
                <CardTitle>Contract Details</CardTitle>
              </div>
              <Button variant="outline" size="sm">
                <Download className="h-4 w-4 mr-2" />
                Download Contract
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-4">
                <div>
                  <p className="text-sm text-muted-foreground">Contract ID</p>
                  <p className="font-mono font-medium">{contractDetails.contractId}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Company</p>
                  <p className="font-medium">{contractDetails.companyName}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Plan</p>
                  <p className="font-medium">{contractDetails.plan}</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Billing Cycle</p>
                  <p className="font-medium">{contractDetails.billingCycle}</p>
                </div>
              </div>
              <div className="space-y-4">
                <div>
                  <p className="text-sm text-muted-foreground">Contract Period</p>
                  <p className="font-medium">
                    {new Date(contractDetails.startDate).toLocaleDateString()} - {new Date(contractDetails.endDate).toLocaleDateString()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Annual Value</p>
                  <p className="text-2xl font-bold">{contractDetails.monthlyValue}/mo</p>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Seats</p>
                  <div className="flex items-center space-x-2">
                    <Users className="h-4 w-4" />
                    <span className="font-medium">
                      {contractDetails.seatsUsed} / {contractDetails.seatsIncluded} used
                    </span>
                  </div>
                  <div className="mt-2 h-2 rounded-full bg-muted overflow-hidden">
                    <div 
                      className="h-full bg-primary rounded-full"
                      style={{ width: `${(contractDetails.seatsUsed / contractDetails.seatsIncluded) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Next Invoice</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center space-x-2">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span>Jan 15, 2025</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Contract Status</CardTitle>
            </CardHeader>
            <CardContent>
              <Badge className="bg-green-100 text-green-800">Active</Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium">Renewal</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm">Auto-renews in 45 days</p>
              <Button variant="link" className="p-0 h-auto mt-1">
                Contact Sales
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Usage Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle>Usage Breakdown</CardTitle>
          <CardDescription>
            Current billing period usage
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Category</TableHead>
                <TableHead>Included</TableHead>
                <TableHead>Used</TableHead>
                <TableHead>Remaining</TableHead>
                <TableHead>Utilization</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {usageBreakdown.map((item) => {
                const included = parseInt(item.included.replace(/,/g, ''));
                const used = parseInt(item.used.replace(/,/g, ''));
                const remaining = included - used;
                const utilization = Math.round((used / included) * 100);
                
                return (
                  <TableRow key={item.category}>
                    <TableCell className="font-medium">{item.category}</TableCell>
                    <TableCell>{item.included} {item.unit}</TableCell>
                    <TableCell>{item.used} {item.unit}</TableCell>
                    <TableCell>{remaining.toLocaleString()} {item.unit}</TableCell>
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <div className="w-24 h-2 rounded-full bg-muted overflow-hidden">
                          <div 
                            className={`h-full rounded-full ${
                              utilization > 90 ? 'bg-red-500' : 
                              utilization > 75 ? 'bg-amber-500' : 'bg-green-500'
                            }`}
                            style={{ width: `${utilization}%` }}
                          />
                        </div>
                        <span className="text-sm text-muted-foreground">{utilization}%</span>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Invoice History */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Receipt className="h-5 w-5" />
              <CardTitle>Invoice History</CardTitle>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Invoice ID</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Period</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoices.map((invoice) => (
                <TableRow key={invoice.id}>
                  <TableCell className="font-mono">{invoice.id}</TableCell>
                  <TableCell>{new Date(invoice.date).toLocaleDateString()}</TableCell>
                  <TableCell>{invoice.period}</TableCell>
                  <TableCell className="font-medium">{invoice.amount}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
                      {invoice.status}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm">
                      <Download className="h-4 w-4 mr-1" />
                      PDF
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Payment Method */}
      <Card>
        <CardHeader>
          <div className="flex items-center space-x-2">
            <CreditCard className="h-5 w-5" />
            <CardTitle>Payment Method</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="rounded-lg border p-3 bg-muted">
                <CreditCard className="h-6 w-6" />
              </div>
              <div>
                <p className="font-medium">Invoice Payment</p>
                <p className="text-sm text-muted-foreground">
                  Invoices are sent to billing@acme.com
                </p>
              </div>
            </div>
            <Button variant="outline">Update</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
