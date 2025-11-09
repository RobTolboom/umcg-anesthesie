# Create a new member page

1. Create a new file in website-content/content/pages/members/
2. Type person's name in entry above. The first and last names should be connected by a dashes and end with .md. For example: ```website-content/content/pages/members/bram-van-ginneken.md```
3. The file should be filled with the following;

```
title: Firstname Lastname
name: Firstname Lastname
pub_name: publication name / pseudonym
template: people-single
picture: people/<image>.png (for adding a picture to a profile see: website-content/docs/adding-picture-to-profile.md. When no picture is availabe, use ```person.png```)
position: Master Student/PhD Candidate/Associate Professor/Assistant Professor/Postdoctoral Researcher/ etc. (pay attention to formulation and capitalisation)
active: yes (change to 'no' when this person is a former employee)
groups: diag, pathology, retina, rse (this determines on which websites the profile will appear. diag is standard, followed by your subgroup)
default_group: diag (the main group of this person, used for internal links. If not set, the first group from 'groups' is used. If set to 'external', internal links and people-circles will load data from external-people.yaml.)
email: example@radboudumc.nl
office: Route ..., room ....
type: (see available types below)

linkedin: link
scholar: link
researcherid: link
orcid: link
twitter: link
show_publication_years: yes (if this tag is not present it will be automatically set to yes)

{Text bio.} 
The bio should be written in the 3rd person. Include your former education, the topic of your research and your supervisors. Include links where possible.
External link: [Text](link), e.g.: [Kaggle website](https://www.kaggle.com/c/prostate-cancer-grade-assessment/overview)
Internal link to person: [member/firstname-lastname], e.g.: [member/geert-litjens]
Internal link to project: [project/projectname], e.g. [project/panda-challenge]}
```

### Available Member Types

The `type` field determines in which section a member appears on the people page. The following types are supported:

| Type Value | Display Section | Use For |
|------------|-----------------|---------|
| `director` | Directors | Department directors and heads |
| `staff` | Staff | General staff members |
| `chair` | Chair | Full professors with chair positions |
| `faculty` | Faculty | Faculty members (doctors, associate/assistant professors) |
| `postdoc` | Scientific staff | Postdoctoral researchers |
| `phd` | Scientific staff | PhD candidates |
| `tech` | Technical staff | Technical staff and engineers |
| `administrative` | Administrative Staff | Administrative personnel |
| `student-assistant` | Student assistants | Student assistants |
| `student` | Visiting researchers | Master/Bachelor students |
| `visiting` | Visiting researchers | Visiting researchers and guests |

**Display order on the people page:**
1. Directors
2. Staff
3. Chair
4. Faculty
5. Scientific staff (postdoc + phd)
6. Technical staff
7. Administrative Staff
8. Student assistants
9. Visiting researchers (student + visiting)

**Example:**
```
type: phd
```

## Multiple Groups

If a person belongs to more than one group (i.e. diag, pathology), the _active_, _type_ and _position_ fields may have different values according to the corresponding group. You can specify a list of values, one for each group. For example, member A belongs to diag and pathology, he/she is active in DIAG and no longer active in pathology and was a student in DIAG and a PhD student in pathology. Then we would have:
```
groups: diag, pathology
active: no, yes
type: student, phd
position: Master Student, PhD candidate
```

4. After editing, select 'Commit changes' at the bottom of the page.

## Guidelines

* Check the other people pages to see what a bio text looks like. Write in the same style.
* Make sure you mention the project you work on as a link.
* Make sure you mention who supervises you, and make this a link, with "[member/bram-van-ginneken]" you create a link to a people page. You can make links by putting the link text between square brackets [ and ] immediately followed by the url between normal parentheses, ( and ). You can refer to publications with "/publications/kars92" as the url text.
* Do not write a title like Prof. or Professor or Dr. before the name of a colleague.
* When you are working temporarily at the group (master students, visiting researchers), state when you will start and how long you will work with us. PhD students should write when they started.

# Editing a member page

1. Go to the member page
2. Select the Edit icon at the bottom of the page
3. You are redirected to the markdown file on GitHub
4. Make your changes and commit
