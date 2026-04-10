'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { 
  FileInvoice, 
  Users, 
  DollarSign, 
  TrendingUp, 
  Plus, 
  Search,
  Menu,
  X,
  Home,
  BarChart3,
  Settings,
  Bell,
  User,
  Brain,
  Shield,
  Zap,
  Clock,
  CheckCircle,
  AlertCircle
} from 'lucide-react'

export default function Home() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('overview')

  const stats = [
    {
      title: 'Total Invoices',
      value: '1,234',
      change: '+12%',
      icon: FileInvoice,
      color: 'text-blue-600'
    },
    {
      title: 'Total Revenue',
      value: '₹2,45,678',
      change: '+23%',
      icon: DollarSign,
      color: 'text-green-600'
    },
    {
      title: 'Active Customers',
      value: '456',
      change: '+8%',
      icon: Users,
      color: 'text-purple-600'
    },
    {
      title: 'Pending Payments',
      value: '23',
      change: '-5%',
      icon: Clock,
      color: 'text-orange-600'
    }
  ]

  const recentInvoices = [
    { id: 'INV-001', customer: 'Acme Corp', amount: '₹5,000', status: 'paid', date: '2024-01-15' },
    { id: 'INV-002', customer: 'Tech Solutions', amount: '₹12,000', status: 'pending', date: '2024-01-14' },
    { id: 'INV-003', customer: 'Global Industries', amount: '₹8,500', status: 'overdue', date: '2024-01-13' },
  ]

  const aiFeatures = [
    {
      title: 'Invoice OCR',
      description: 'Scan and extract data from paper invoices',
      icon: Brain,
      color: 'bg-blue-500'
    },
    {
      title: 'Fraud Detection',
      description: 'Real-time suspicious activity alerts',
      icon: Shield,
      color: 'bg-red-500'
    },
    {
      title: 'Smart Categorization',
      description: 'Automatic expense classification',
      icon: Zap,
      color: 'bg-yellow-500'
    },
    {
      title: 'Predictive Analytics',
      description: 'Business forecasting and insights',
      icon: TrendingUp,
      color: 'bg-green-500'
    }
  ]

  const navigationItems = [
    { icon: Home, label: 'Dashboard', active: true },
    { icon: FileInvoice, label: 'Invoices', active: false },
    { icon: Users, label: 'Customers', active: false },
    { icon: BarChart3, label: 'Analytics', active: false },
    { icon: Settings, label: 'Settings', active: false },
  ]

  const getStatusBadge = (status: string) => {
    const variants: Record<string, { variant: 'default' | 'secondary' | 'destructive' | 'outline'; label: string }> = {
      paid: { variant: 'default', label: 'Paid' },
      pending: { variant: 'secondary', label: 'Pending' },
      overdue: { variant: 'destructive', label: 'Overdue' }
    }
    return variants[status] || { variant: 'outline', label: status }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile Header */}
      <header className="lg:hidden bg-white shadow-sm border-b border-gray-200 sticky top-0 z-50">
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center space-x-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="p-2"
            >
              {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </Button>
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                <FileInvoice className="h-4 w-4 text-white" />
              </div>
              <span className="font-semibold text-gray-900">Mobi Invoice</span>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Button variant="ghost" size="sm" className="p-2">
              <Bell className="h-5 w-5" />
            </Button>
            <Button variant="ghost" size="sm" className="p-2">
              <User className="h-5 w-5" />
            </Button>
          </div>
        </div>
      </header>

      {/* Mobile Sidebar Overlay */}
      {isMobileMenuOpen && (
        <div 
          className="lg:hidden fixed inset-0 bg-black bg-opacity-50 z-40"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`
        fixed lg:static inset-y-0 left-0 z-50 w-64 bg-white shadow-lg transform transition-transform duration-300 ease-in-out
        ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg flex items-center justify-center">
                <FileInvoice className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">Mobi Invoice</h1>
                <p className="text-xs text-gray-500">AI-Powered Platform</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-2">
            {navigationItems.map((item, index) => (
              <Button
                key={index}
                variant={item.active ? "default" : "ghost"}
                className="w-full justify-start"
                onClick={() => {
                  // Handle navigation
                  setIsMobileMenuOpen(false)
                }}
              >
                <item.icon className="h-4 w-4 mr-3" />
                {item.label}
              </Button>
            ))}
          </nav>

          {/* User Section */}
          <div className="p-4 border-t border-gray-200">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-gray-300 rounded-full flex items-center justify-center">
                <User className="h-4 w-4 text-gray-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">John Doe</p>
                <p className="text-xs text-gray-500 truncate">john@example.com</p>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="lg:ml-64">
        {/* Desktop Header */}
        <header className="hidden lg:block bg-white shadow-sm border-b border-gray-200">
          <div className="px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
                <p className="text-sm text-gray-500">Welcome back! Here's your business overview.</p>
              </div>
              <div className="flex items-center space-x-3">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <input
                    type="text"
                    placeholder="Search..."
                    className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>
                <Button variant="outline" size="sm">
                  <Bell className="h-4 w-4" />
                </Button>
                <Button variant="outline" size="sm">
                  <User className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Content */}
        <div className="p-4 lg:p-6">
          {/* Quick Actions - Mobile First */}
          <div className="mb-6">
            <div className="flex flex-wrap gap-2 lg:hidden">
              <Button size="sm" className="flex-1 min-w-0">
                <Plus className="h-4 w-4 mr-2" />
                Invoice
              </Button>
              <Button variant="outline" size="sm" className="flex-1 min-w-0">
                <Users className="h-4 w-4 mr-2" />
                Customer
              </Button>
              <Button variant="outline" size="sm" className="flex-1 min-w-0">
                <BarChart3 className="h-4 w-4 mr-2" />
                Reports
              </Button>
            </div>
          </div>

          {/* Stats Grid - Responsive */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            {stats.map((stat, index) => (
              <Card key={index} className="hover:shadow-md transition-shadow">
                <CardContent className="p-4 lg:p-6">
                  <div className="flex items-center justify-between mb-2">
                    <stat.icon className={`h-5 w-5 lg:h-6 lg:w-6 ${stat.color}`} />
                    <Badge variant="outline" className="text-xs">
                      {stat.change}
                    </Badge>
                  </div>
                  <div className="space-y-1">
                    <p className="text-lg lg:text-2xl font-bold text-gray-900">{stat.value}</p>
                    <p className="text-xs lg:text-sm text-gray-500">{stat.title}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Main Content Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
            <TabsList className="grid w-full grid-cols-3 lg:w-auto">
              <TabsTrigger value="overview" className="text-xs lg:text-sm">Overview</TabsTrigger>
              <TabsTrigger value="invoices" className="text-xs lg:text-sm">Invoices</TabsTrigger>
              <TabsTrigger value="ai-features" className="text-xs lg:text-sm">AI Features</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-4">
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                {/* Recent Invoices */}
                <Card className="xl:col-span-2">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">Recent Invoices</CardTitle>
                      <Button variant="outline" size="sm">View All</Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {recentInvoices.map((invoice, index) => {
                        const status = getStatusBadge(invoice.status)
                        return (
                          <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-gray-900 truncate">{invoice.id}</p>
                              <p className="text-sm text-gray-500 truncate">{invoice.customer}</p>
                            </div>
                            <div className="flex items-center space-x-2">
                              <span className="text-sm font-medium">{invoice.amount}</span>
                              <Badge variant={status.variant} className="text-xs">
                                {status.label}
                              </Badge>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </CardContent>
                </Card>

                {/* Quick Stats */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg">Quick Stats</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <CheckCircle className="h-4 w-4 text-green-500" />
                        <span className="text-sm">Paid This Month</span>
                      </div>
                      <span className="font-medium">₹45,678</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Clock className="h-4 w-4 text-orange-500" />
                        <span className="text-sm">Pending</span>
                      </div>
                      <span className="font-medium">₹12,345</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <AlertCircle className="h-4 w-4 text-red-500" />
                        <span className="text-sm">Overdue</span>
                      </div>
                      <span className="font-medium">₹3,456</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="invoices" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between space-y-2 sm:space-y-0">
                    <CardTitle>All Invoices</CardTitle>
                    <div className="flex space-x-2">
                      <Button variant="outline" size="sm">Filter</Button>
                      <Button size="sm">
                        <Plus className="h-4 w-4 mr-2" />
                        New Invoice
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left py-2 text-sm font-medium">Invoice</th>
                          <th className="text-left py-2 text-sm font-medium">Customer</th>
                          <th className="text-left py-2 text-sm font-medium">Amount</th>
                          <th className="text-left py-2 text-sm font-medium">Status</th>
                          <th className="text-left py-2 text-sm font-medium hidden sm:table-cell">Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recentInvoices.map((invoice, index) => {
                          const status = getStatusBadge(invoice.status)
                          return (
                            <tr key={index} className="border-b">
                              <td className="py-3 text-sm">{invoice.id}</td>
                              <td className="py-3 text-sm">{invoice.customer}</td>
                              <td className="py-3 text-sm font-medium">{invoice.amount}</td>
                              <td className="py-3">
                                <Badge variant={status.variant} className="text-xs">
                                  {status.label}
                                </Badge>
                              </td>
                              <td className="py-3 text-sm hidden sm:table-cell">{invoice.date}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="ai-features" className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {aiFeatures.map((feature, index) => (
                  <Card key={index} className="hover:shadow-md transition-shadow">
                    <CardHeader>
                      <div className="flex items-center space-x-3">
                        <div className={`w-10 h-10 ${feature.color} rounded-lg flex items-center justify-center`}>
                          <feature.icon className="h-5 w-5 text-white" />
                        </div>
                        <CardTitle className="text-lg">{feature.title}</CardTitle>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-gray-600 mb-4">{feature.description}</p>
                      <Button variant="outline" size="sm" className="w-full">
                        Learn More
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  )
}