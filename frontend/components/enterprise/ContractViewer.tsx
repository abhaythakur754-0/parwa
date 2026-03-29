'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Separator } from '@/components/ui/separator';
import {
  Download,
  ExternalLink,
  Calendar,
  Clock,
  Users,
  DollarSign,
  FileText,
  PenLine,
  CheckCircle
} from 'lucide-react';

/**
 * Contract Viewer Component
 * 
 * Displays contract details, signature status, and document history
 * for enterprise customers.
 */

interface ContractViewerProps {
  contractId?: string;
}

export function ContractViewer({ contractId = 'ENT-2024-001' }: ContractViewerProps) {
  const [activeTab, setActiveTab] = useState('details');

  const contract = {
    id: contractId,
    status: 'signed',
    version: '2.0',
    createdAt: '2024-01-10',
    signedAt: '2024-01-15',
    startDate: '2024-01-15',
    endDate: '2025-01-14',
    autoRenew: true,
    value: '$59,400.00',
    currency: 'USD'
  };

  const signatures = [
    {
      id: 1,
      signer: 'John Smith',
      title: 'CEO',
      email: 'john.smith@acme.com',
      signedAt: '2024-01-15T10:30:00Z',
      ipAddress: '192.168.1.1'
    },
    {
      id: 2,
      signer: 'Jane Doe',
      title: 'VP Operations, PARWA',
      email: 'jane.doe@parwa.ai',
      signedAt: '2024-01-15T14:45:00Z',
      ipAddress: '10.0.0.1'
    }
  ];

  const documents = [
    {
      id: 1,
      name: 'Enterprise Agreement',
      version: '2.0',
      signedAt: '2024-01-15'
    },
    {
      id: 2,
      name: 'Data Processing Agreement',
      version: '1.5',
      signedAt: '2024-01-15'
    },
    {
      id: 3,
      name: 'Service Level Agreement',
      version: '2.0',
      signedAt: '2024-01-15'
    }
  ];

  const renewalTerms = [
    { term: 'Auto-Renewal', value: 'Enabled' },
    { term: 'Notice Period', value: '30 days' },
    { term: 'Price Adjustment', value: 'Capped at 5% annually' }
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Contract {contract.id}</h2>
          <p className="text-muted-foreground">
            Enterprise Agreement v{contract.version}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge className="bg-green-100 text-green-800">
            <CheckCircle className="h-3 w-3 mr-1" />
            Signed
          </Badge>
          <Button variant="outline">
            <Download className="h-4 w-4 mr-2" />
            Download PDF
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Contract Value</p>
                <p className="text-xl font-bold">{contract.value}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Calendar className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Start Date</p>
                <p className="text-xl font-bold">
                  {new Date(contract.startDate).toLocaleDateString()}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">End Date</p>
                <p className="text-xl font-bold">
                  {new Date(contract.endDate).toLocaleDateString()}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center space-x-2">
              <Users className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-sm text-muted-foreground">Seats</p>
                <p className="text-xl font-bold">50</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="details">Contract Details</TabsTrigger>
          <TabsTrigger value="signatures">Signatures</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="renewal">Renewal Terms</TabsTrigger>
        </TabsList>

        <TabsContent value="details" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Contract Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="text-sm text-muted-foreground">Contract ID</p>
                    <p className="font-mono">{contract.id}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Version</p>
                    <p>{contract.version}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Created</p>
                    <p>{new Date(contract.createdAt).toLocaleDateString()}</p>
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Signed</p>
                    <p>{new Date(contract.signedAt).toLocaleDateString()}</p>
                  </div>
                </div>

                <Separator />

                <div>
                  <h4 className="font-medium mb-2">Key Terms</h4>
                  <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground">
                    <li>50 enterprise seats included</li>
                    <li>99.9% uptime SLA guarantee</li>
                    <li>24/7 priority support</li>
                    <li>Dedicated Customer Success Manager</li>
                    <li>SSO/SAML integration</li>
                    <li>API access with 100,000 calls/month</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="signatures">
          <Card>
            <CardHeader>
              <CardTitle>Signature History</CardTitle>
              <CardDescription>
                All parties who have signed this contract
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Signer</TableHead>
                    <TableHead>Title</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Signed At</TableHead>
                    <TableHead>IP Address</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {signatures.map((sig) => (
                    <TableRow key={sig.id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center space-x-2">
                          <PenLine className="h-4 w-4 text-green-500" />
                          {sig.signer}
                        </div>
                      </TableCell>
                      <TableCell>{sig.title}</TableCell>
                      <TableCell>{sig.email}</TableCell>
                      <TableCell>
                        {new Date(sig.signedAt).toLocaleString()}
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        {sig.ipAddress}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="documents">
          <Card>
            <CardHeader>
              <CardTitle>Contract Documents</CardTitle>
              <CardDescription>
                All documents included in this agreement
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-4 rounded-lg border"
                  >
                    <div className="flex items-center space-x-3">
                      <FileText className="h-5 w-5 text-muted-foreground" />
                      <div>
                        <p className="font-medium">{doc.name}</p>
                        <p className="text-sm text-muted-foreground">
                          Version {doc.version} • Signed {doc.signedAt}
                        </p>
                      </div>
                    </div>
                    <Button variant="ghost" size="sm">
                      <ExternalLink className="h-4 w-4 mr-1" />
                      View
                    </Button>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="renewal">
          <Card>
            <CardHeader>
              <CardTitle>Renewal Terms</CardTitle>
              <CardDescription>
                Terms for contract renewal and termination
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Term</TableHead>
                      <TableHead>Value</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {renewalTerms.map((term, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-medium">{term.term}</TableCell>
                        <TableCell>{term.value}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                <div className="p-4 rounded-lg bg-muted">
                  <h4 className="font-medium mb-2">Cancellation Policy</h4>
                  <p className="text-sm text-muted-foreground">
                    Either party may terminate this agreement with 30 days written notice
                    prior to the end of the current term. Early termination may be subject
                    to a termination fee equal to 25% of the remaining contract value.
                  </p>
                </div>

                <Button variant="outline" className="w-full">
                  Contact Sales About Renewal Options
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
