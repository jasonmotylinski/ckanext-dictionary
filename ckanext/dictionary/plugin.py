import ckan.plugins as p


class Data_DictionaryPlugin(p.SingletonPlugin):
    """data dictionary plugin."""

    p.implements(p.IRoutes, inherit=True)
    p.implements(p.IConfigurer)

    def before_map(self, map):

        map.connect('dataset_edit_dictionary', 
                    '/dataset/dictionary/edit/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action='edit_dictionary',
                    ckan_icon='edit')

        map.connect('data dict button', 
                    '/dataset/dictionary/new_dict/{id}',
                    controller='ckanext.dictionary.controller:DDController',
                    action="new_data_dictionary")

        map.connect('api_dictionary_update', 
                    '/api/action/dictionary_update',
                    controller='ckanext.dictionary.controller:ApiController',
                    action='dictionary_update')

        return map

    def update_config(self, config_):
        p.toolkit.add_template_directory(config_, 'templates')
        p.toolkit.add_public_directory(config_, 'public')
        p.toolkit.add_resource('fanstatic', 'dictionary')
