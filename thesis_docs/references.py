"""
Harvard reference data for the thesis (used by format_draft.py).

Sources, both the authors' own lists:
  - proposal draft final.pdf reference list (Harvard), copied verbatim except where noted;
  - writting/Chapter 2.docx reference list (IEEE [1]-[27]), rewritten in Harvard form.
Corrections: Qi et al. (missing bracket); Beale (venue taken from the paper itself:
Appl. Syst. Innov. 2026, 9, 17); Zhao et al. uses the published ACL 2026 version.

CITATION_FIXES rewrites malformed in-text citations found in the draft; KEY maps each normalised
citation to one entry. Citations with no entry in either list are left unchanged and reported.
"""
from __future__ import annotations

ENTRIES = {
    "Ahmed2024": "Ahmed, Z., Shanto, S.S., Rime, M.H.K., Morol, M.K., Fahad, N., Hossen, M.J. and Abdullah-Al-Jubair, M. (2024) 'The generative AI landscape in education: Mapping the terrain of opportunities, challenges, and student perception', IEEE Access, 12, pp. 147023–147048.",
    "Anderson2001": "Anderson, L.W. and Krathwohl, D.R. (eds.) (2001) A taxonomy for learning, teaching, and assessing: A revision of Bloom's taxonomy of educational objectives. New York: Longman.",
    "Beale2026": "Beale, R. (2026) 'Beyond answers: Pedagogical design rationale for multi-persona AI tutors', Applied System Innovation, 9, 17.",
    "Biggs1982": "Biggs, J.B. and Collis, K.F. (1982) Evaluating the quality of learning: The SOLO taxonomy. New York: Academic Press.",
    "Black2009": "Black, P. and Wiliam, D. (2009) 'Developing the theory of formative assessment', Educational Assessment, Evaluation and Accountability, 21, pp. 5–31. doi:10.1007/s11092-008-9068-5.",
    "Blasco2024": "Blasco, A. and Charisi, V. (2024) 'AI chatbots in K-12 education: An experimental study of Socratic vs. non-Socratic approaches and the role of step-by-step reasoning', SSRN Electronic Journal [Preprint], revised 2025.",
    "Chi2002": "Chi, M.T.H. and Roscoe, R.D. (2002) 'The processes and challenges of conceptual change', in Limón, M. and Mason, L. (eds.) Reconsidering conceptual change: Issues in theory and practice. Dordrecht: Kluwer Academic Publishers, pp. 3–27.",
    "Delic2016": "Delić, H. and Bećirović, S. (2016) 'Socratic method as an approach to teaching', European Researcher. Series A, 111(10), pp. 511–517.",
    "Dong2025": "Dong, Z., Chen, J.Y. and Wu, F. (2025) 'LLM-driven cognitive diagnosis with SOLO taxonomy: A model-agnostic framework', Frontiers of Digital Education, 2(2), 20.",
    "Gabrovsek2025": "Gabrovšek, R. and Rihtaršič, D. (2025) 'Custom generative artificial intelligence tutors in action: An experimental evaluation of prompt strategies in STEM education', Sustainability, 17, 9508.",
    "Jabbour2025": "Jabbour, J. et al. (2025) 'SocratiQ: A generative AI-powered learning companion for personalized education and broader accessibility', Workshop on Computer Architecture Education (WCAE '25).",
    "Kaczmarczyk2010": "Kaczmarczyk, L.C., Petrick, E.R., East, J.P. and Herman, G.L. (2010) 'Identifying student misconceptions of programming', Proceedings of the 41st ACM Technical Symposium on Computer Science Education (SIGCSE '10), pp. 107–111.",
    "Kirschner2006": "Kirschner, P.A., Sweller, J. and Clark, R.E. (2006) 'Why minimal guidance during instruction does not work: An analysis of the failure of constructivist, discovery, problem-based, experiential, and inquiry-based teaching', Educational Psychologist, 41(2), pp. 75–86.",
    "LiChang2026": "Li, K.-H. and Chang, C.-K. (2026) 'Agentic AI as a dual-role lecturer and teaching assistant: Effects on learner autonomy, self-regulated learning, and intrinsic motivation in university-level EFL education', Frontiers in Psychology, 17, 1847607.",
    "Li2024": "Li, X. et al. (2024) 'A survey on LLM-based multi-agent systems: Workflow, infrastructure, and challenges', Vicinagearth, 1, 9.",
    "Liu2024": "Liu, J., Huang, Z., Xiao, T., Sha, J., Wu, J., Liu, Q., Wang, S. and Chen, E. (2024) 'SocraticLM: Exploring Socratic personalized teaching with large language models', Advances in Neural Information Processing Systems, 37, pp. 85693–85721.",
    "Liu2025": "Liu, Z., Agrawal, P., Singhal, S., Madaan, V., Kumar, M. and Verma, P.K. (2025) 'LPITutor: An LLM based personalized intelligent tutoring system using RAG and prompt engineering', PeerJ Computer Science, 11, e2991.",
    "Lubbe2025": "Lubbe, A., Marais, E. and Kruger, D. (2025) 'Cultivating independent thinkers: The triad of artificial intelligence, Bloom's taxonomy and critical thinking in assessment pedagogy', Education and Information Technologies, 30, pp. 17589–17622.",
    "Maurya2025": "Maurya, K.K., Srivatsa, K.A., Petukhova, K. and Kochmar, E. (2025) 'Unifying AI tutor evaluation: An evaluation taxonomy for pedagogical ability assessment of LLM-powered AI tutors', Proceedings of the 2025 Conference of the Nations of the Americas Chapter of the Association for Computational Linguistics, pp. 1234–1251.",
    "Ng2024": "Ng, D.B. et al. (2024) 'When I say … Socratic questioning', Medical Education. doi:10.1111/medu.15397.",
    "Nichols1994": "Nichols, P.D. (1994) 'A framework for developing cognitively diagnostic assessments', Review of Educational Research, 64(4), pp. 575–603.",
    "Ouyang2021": "Ouyang, F. and Jiao, P. (2021) 'Three paradigms of AIEd: AI-directed, AI-supported, and AI-empowered', Computers and Education: Artificial Intelligence, 2, 100020.",
    "Pallant2026": "Pallant, J.L., Blijlevens, J., Campbell, A. and Jopp, R. (2026) 'Mastering knowledge: The impact of generative AI on student learning outcomes', Studies in Higher Education, 51(4), pp. 714–735.",
    "Posner1982": "Posner, G.J., Strike, K.A., Hewson, P.W. and Gertzog, W.A. (1982) 'Accommodation of a scientific conception: Toward a theory of conceptual change', Science Education, 66(2), pp. 211–227.",
    "Qi2025": "Qi, C., Jia, L., Wei, Y., Jiang, Y.-H. and Gu, X. (2025) 'IntelliChain: An integrated framework for enhanced Socratic method dialogue with LLMs and knowledge graphs', Proceedings of the 28th Global Chinese Conference on Computers in Education (GCCCE 2025), pp. 116–121.",
    "Rus2013": "Rus, V., D'Mello, S., Hu, X. and Graesser, A.C. (2013) 'Recent advances in conversational intelligent tutoring systems', AI Magazine, 34(3), pp. 42–54.",
    "Rus2015": "Rus, V., Niraula, N.B. and Banjade, R. (2015) 'DeepTutor: An effective, online intelligent tutoring system that promotes deep learning', Proceedings of the AAAI Conference on Artificial Intelligence, 29(1).",
    "Sweller1988": "Sweller, J. (1988) 'Cognitive load during problem solving: Effects on learning', Cognitive Science, 12(2), pp. 257–285.",
    "Vygotsky1978": "Vygotsky, L.S. (1978) Mind in society: The development of higher psychological processes. Cambridge, MA: Harvard University Press.",
    "Wang2025": "Wang, T., Zhan, Y., Lian, J., Hu, Z., Yuan, N.J., Zhang, Q., Xie, X. and Xiong, H. (2025) 'LLM-powered multi-agent framework for goal-oriented learning in intelligent tutoring system', Companion Proceedings of the ACM Web Conference 2025.",
    "Wood1976": "Wood, D., Bruner, J.S. and Ross, G. (1976) 'The role of tutoring in problem solving', Journal of Child Psychology and Psychiatry, 17(2), pp. 89–100.",
    "YaoHuang2026": "Yao, F. and Huang, Z. (2026) 'A dynamic AI scaffolding system based on ZPD theory: Reducing cognitive load and enhancing transfer in mathematical proof learning', Journal of Natural Science Education, 3(1), pp. 18–26.",
    "Zhai2024": "Zhai, C., Wibowo, S. and Li, L.D. (2024) 'The effects of over-reliance on AI dialogue systems on students' cognitive abilities: A systematic review', Smart Learning Environments, 11, 28.",
    "ZhangS2024": "Zhang, S., Zhao, X., Zhou, T. and Kim, J.H. (2024) 'Do you have AI dependency? The roles of self-efficacy, stress, and expectations', International Journal of Educational Technology in Higher Education, 21, 34.",
    "ZhangX2025": "Zhang, X. et al. (2025) 'EduPlanner: LLM-based multi-agent systems for customized and intelligent instructional design', IEEE Transactions on Learning Technologies, 18, pp. 416–427.",
    "Zhao2026": "Zhao, J., Knežević, M. and Käser, T. (2026) 'Evaluating answer leakage robustness of LLM tutors against adversarial student attacks', Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics, pp. 30588–30617.",
}

# Malformed in-text citations in the draft -> normalised Harvard form (applied to paragraph text).
CITATION_FIXES = [
    ("(Anitia Lubbe et ,aL., 2025)", "(Lubbe et al., 2025)"),
    ("(Bećirović, 2016)", "(Delić and Bećirović, 2016)"),
    ("Li & Chang, 2026", "Li and Chang, 2026"),
    ("(Linda Harasim,book 2012 )", "(Harasim, 2012)"),
    ("(Linda Harasim,book 2012)", "(Harasim, 2012)"),
    ("(Russell Beale2025)", "(Beale, 2026)"),
    ("Russell Beale2025", "Beale, 2026"),
    ("(Tianfu Wang et al.2025)", "(Wang et al., 2025)"),
    ("Tianfu Wang et al.2025", "Wang et al., 2025"),
    ("Vasile Rus   et al   ,2015", "Rus et al., 2015"),
    ("Vasile Rus  et al ,2013", "Rus et al., 2013"),
    ("Vasile Rus et al .,2015,", "Rus et al., 2015;"),
    ("Vasile Rus et al.,2013", "Rus et al., 2013"),
    ("Xueqiao Zhang et al., 2025", "Zhang, X. et al., 2025"),
    ("Zhiang Dong et al.,2025", "Dong et al., 2025"),
    ("Dong et al. ,2025", "Dong et al., 2025"),
    ("(Liu et al. (2025)", "(Liu et al., 2025)"),
    ("Pallant et al. (2025)", "Pallant et al. (2026)"),
    ("Zhang et al. (2024)", "Zhang, S. et al. (2024)"),
]

# Normalised citation (surname part, year) -> entry key.
KEY = {
    ("Ahmed", "2024"): "Ahmed2024", ("Anderson", "2001"): "Anderson2001", ("Beale", "2026"): "Beale2026",
    ("Biggs", "1982"): "Biggs1982", ("Black", "2009"): "Black2009", ("Blasco", "2024"): "Blasco2024",
    ("Chi", "2002"): "Chi2002", ("Delić", "2016"): "Delic2016", ("Dong", "2025"): "Dong2025",
    ("Gabrovšek", "2025"): "Gabrovsek2025", ("Jabbour", "2025"): "Jabbour2025",
    ("Kaczmarczyk", "2010"): "Kaczmarczyk2010", ("Kirschner", "2006"): "Kirschner2006",
    ("Li and Chang", "2026"): "LiChang2026", ("Li", "2024"): "Li2024", ("Liu", "2024"): "Liu2024",
    ("Liu", "2025"): "Liu2025", ("Lubbe", "2025"): "Lubbe2025", ("Maurya", "2025"): "Maurya2025",
    ("Ng", "2024"): "Ng2024", ("Nichols", "1994"): "Nichols1994", ("Ouyang", "2021"): "Ouyang2021",
    ("Pallant", "2026"): "Pallant2026", ("Posner", "1982"): "Posner1982", ("Qi", "2025"): "Qi2025",
    ("Rus", "2013"): "Rus2013", ("Rus", "2015"): "Rus2015", ("Sweller", "1988"): "Sweller1988",
    ("Vygotsky", "1978"): "Vygotsky1978", ("Wang", "2025"): "Wang2025", ("Wood", "1976"): "Wood1976",
    ("Yao", "2026"): "YaoHuang2026", ("Zhai", "2024"): "Zhai2024", ("Zhang, S.", "2024"): "ZhangS2024",
    ("Zhang, X.", "2025"): "ZhangX2025", ("Zhao", "2026"): "Zhao2026",
}
