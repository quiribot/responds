from responds.group import Group, prefix, route


@prefix("/stuff")
class TestGroup(Group):
    @route("/test")
    async def stuff_test(self, ctx):
        return b"stuff test\n"
