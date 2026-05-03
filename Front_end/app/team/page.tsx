'use client'

import { Users, Github, Linkedin, Mail, Twitter, ChevronRight } from 'lucide-react'
import { FadeIn, StaggerContainer, StaggerItem } from '@/components/ui/fade-in'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import Link from 'next/link'

// Placeholder data - to be replaced later
const TEAM_MEMBERS = [
  {
    id: 1,
    name: 'Team Member 1',
    role: 'Lead Developer',
    avatar: 'TM',
    color: 'from-primary to-primary/60',
    bio: 'Passionate about building scalable AI systems and crafting beautiful user interfaces.',
    socials: { github: '#', linkedin: '#', twitter: '#' }
  },
  {
    id: 2,
    name: 'Team Member 2',
    role: 'AI Researcher',
    avatar: 'TM',
    color: 'from-accent to-accent/60',
    bio: 'Specializes in NLP, retrieval-augmented generation, and fine-tuning large language models.',
    socials: { github: '#', linkedin: '#', twitter: '#' }
  },
  {
    id: 3,
    name: 'Team Member 3',
    role: 'Data Scientist',
    avatar: 'TM',
    color: 'from-chart-3 to-chart-3/60',
    bio: 'Expert in vector databases, embedding models, and data pipeline optimization.',
    socials: { github: '#', linkedin: '#', twitter: '#' }
  },
  {
    id: 4,
    name: 'Team Member 4',
    role: 'UX/UI Designer',
    avatar: 'TM',
    color: 'from-chart-5 to-chart-5/60',
    bio: 'Creates intuitive, accessible, and stunning digital experiences for complex data tools.',
    socials: { github: '#', linkedin: '#', twitter: '#' }
  }
]

export default function TeamPage() {
  return (
    <div className="min-h-full px-6 py-8 overflow-x-hidden">
      <div className="mx-auto max-w-6xl space-y-10">
        {/* Header */}
        <FadeIn direction="up">
          <div className="relative overflow-hidden rounded-2xl surface p-10">
            {/* Background Orbs */}
            <div className="orb orb-amber" style={{ width: 250, height: 250, top: -80, right: -40 }} />
            <div className="orb orb-teal" style={{ width: 180, height: 180, bottom: -40, left: '10%' }} />
            
            <div className="relative z-10 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div className="max-w-xl">
                <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary mb-4">
                  <Users className="h-3.5 w-3.5" />
                  Meet the Innovators
                </div>
                <h1 className="text-3xl font-bold tracking-tight lg:text-4xl">
                  The <span className="text-gradient">Minds</span> Behind the Engine
                </h1>
                <p className="mt-4 text-base text-muted-foreground leading-relaxed">
                  We are a dedicated team of engineers, researchers, and designers passionate about making AI accessible, reliable, and powerful for everyone.
                </p>
              </div>
            </div>
          </div>
        </FadeIn>

        {/* Team Grid */}
        <StaggerContainer className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4 pt-4">
          {TEAM_MEMBERS.map((member) => (
            <StaggerItem key={member.id} className="group h-full">
              <Card className="h-full overflow-hidden border-border/40 bg-card/40 backdrop-blur-sm transition-all hover:-translate-y-1 hover:border-primary/30 hover:shadow-xl hover:shadow-primary/5">
                <CardHeader className="relative pb-0 pt-6">
                  {/* Avatar Circle */}
                  <div className="relative mx-auto h-24 w-24">
                    <div className="absolute inset-0 rounded-full bg-muted/40 blur-md group-hover:bg-primary/20 transition-colors" />
                    <div className={`relative flex h-full w-full items-center justify-center rounded-full bg-gradient-to-br ${member.color} text-2xl font-bold text-white shadow-inner`}>
                      {member.avatar}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="mt-6 text-center pb-6 px-6">
                  <h3 className="font-bold text-lg">{member.name}</h3>
                  <p className="text-sm font-medium text-primary/80 mt-1">{member.role}</p>
                  
                  <div className="h-px w-full bg-border/40 my-4" />
                  
                  <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3">
                    {member.bio}
                  </p>
                  
                  <div className="mt-6 flex items-center justify-center gap-3">
                    <Link href={member.socials.github} className="text-muted-foreground hover:text-foreground transition-colors p-2 bg-muted/30 hover:bg-muted/60 rounded-full">
                      <Github className="h-4 w-4" />
                    </Link>
                    <Link href={member.socials.linkedin} className="text-muted-foreground hover:text-[#0A66C2] transition-colors p-2 bg-muted/30 hover:bg-muted/60 rounded-full">
                      <Linkedin className="h-4 w-4" />
                    </Link>
                    <Link href={member.socials.twitter} className="text-muted-foreground hover:text-foreground transition-colors p-2 bg-muted/30 hover:bg-muted/60 rounded-full">
                      <Twitter className="h-4 w-4" />
                    </Link>
                  </div>
                </CardContent>
              </Card>
            </StaggerItem>
          ))}
        </StaggerContainer>

        {/* Join Us CTA */}
        <FadeIn direction="up" delay={0.4}>
          <div className="mt-12 surface flex flex-col items-center justify-center rounded-2xl border-dashed border-2 border-border/60 p-10 text-center transition-colors hover:border-primary/50 hover:bg-primary/5">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-4">
              <Mail className="h-5 w-5 text-primary" />
            </div>
            <h3 className="text-lg font-bold">Contact the Team</h3>
            <p className="mt-2 text-sm text-muted-foreground max-w-sm">
              Have questions about the architecture or want to contribute? We&apos;d love to hear from you.
            </p>
            <button className="mt-6 inline-flex items-center gap-2 rounded-full bg-foreground px-5 py-2 text-sm font-medium text-background transition-transform hover:scale-105">
              Get in touch
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </FadeIn>
      </div>
    </div>
  )
}
